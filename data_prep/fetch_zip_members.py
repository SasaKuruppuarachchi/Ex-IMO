#!/usr/bin/env python3
"""Extract selected members of a remote zip using HTTP range requests only.

The zip may be published as raw byte chunks that are meant to be concatenated
(e.g. TII-RATM's `piloted_zipchunk01..07`). Each member is stream-decompressed,
checked against the CRC32 and size recorded in the zip central directory, and
written atomically. Re-running skips members already present with a matching
CRC32, so the script is resumable.

Standard library only, so it runs on the host without the project container.

Example:
  python3 -I data_prep/fetch_zip_members.py \
      --base https://github.com/tii-racing/drone-racing-dataset/releases/download/v3.0.0 \
      --chunks autonomous_zipchunk01,autonomous_zipchunk02,autonomous_zipchunk03 \
      --out data/raw/tii_ratm/v3.0.0 \
      --exclude '/(camera|label)_flight-[^/]+\\.zip$' \
      --index-out data/manifests/tii_ratm_autonomous_members.json
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import struct
import sys
import time
import urllib.request
import zlib

BLOCK = 1 << 20


def head_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


class ChunkedRemote:
    """Random access over the concatenation of several remote files."""

    def __init__(self, base, names):
        self.urls = [f"{base}/{n}" for n in names]
        self.sizes = [head_size(u) for u in self.urls]
        self.starts = [sum(self.sizes[:i]) for i in range(len(self.sizes))]
        self.total = sum(self.sizes)

    def _segments(self, off, n):
        while n > 0:
            i = max(j for j, s in enumerate(self.starts) if s <= off)
            lo = off - self.starts[i]
            take = min(n, self.sizes[i] - lo)
            yield self.urls[i], lo, lo + take - 1
            off += take
            n -= take

    def stream(self, off, n):
        for url, a, b in self._segments(off, n):
            req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status != 206:
                    raise IOError(f"expected HTTP 206 from {url}, got {r.status}")
                got = 0
                while True:
                    blk = r.read(BLOCK)
                    if not blk:
                        break
                    got += len(blk)
                    yield blk
                if got != b - a + 1:
                    raise IOError(f"short read from {url}: {got} of {b - a + 1} bytes")

    def read(self, off, n):
        return b"".join(self.stream(off, n))


def central_directory(rz):
    tail = rz.read(max(0, rz.total - 70000), min(70000, rz.total))
    e = tail.rfind(b"PK\x05\x06")
    if e < 0:
        raise ValueError("end-of-central-directory record not found")
    _, _, _, _, _, cdsize, cdoff, _ = struct.unpack("<IHHHHIIH", tail[e:e + 22])
    z = tail.rfind(b"PK\x06\x07")
    if z >= 0:
        rec = rz.read(struct.unpack("<Q", tail[z + 8:z + 16])[0], 56)
        assert rec[:4] == b"PK\x06\x06", "bad ZIP64 end-of-central-directory record"
        _, cdsize, cdoff = struct.unpack("<QQQ", rec[32:56])
    cd = rz.read(cdoff, cdsize)
    entries, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method, crc, csize, usize, fnl, exl, cml = struct.unpack("<H4xIIIHHH", cd[p + 10:p + 34])
        lho = struct.unpack("<I", cd[p + 42:p + 46])[0]
        name = cd[p + 46:p + 46 + fnl].decode("utf-8", "replace")
        extra = cd[p + 46 + fnl:p + 46 + fnl + exl]
        q = 0
        while q + 4 <= len(extra):
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:  # ZIP64 extended information
                vals = list(struct.unpack("<" + "Q" * (hl // 8), extra[q + 4:q + 4 + 8 * (hl // 8)]))
                if usize == 0xFFFFFFFF:
                    usize = vals.pop(0)
                if csize == 0xFFFFFFFF:
                    csize = vals.pop(0)
                if lho == 0xFFFFFFFF:
                    lho = vals.pop(0)
            q += 4 + hl
        entries.append(dict(name=name, method=method, crc32=crc, csize=csize, usize=usize, lho=lho))
        p += 46 + fnl + exl + cml
    return entries


def safe_target(out, name):
    parts = name.replace("\\", "/").split("/")
    if name.startswith("/") or any(x in ("..",) for x in parts) or re.match(r"^[A-Za-z]:", name):
        raise ValueError(f"unsafe member path: {name!r}")
    return os.path.join(out, *[x for x in parts if x])


def file_crc_sha(path):
    crc, h = 0, hashlib.sha256()
    with open(path, "rb") as f:
        while blk := f.read(BLOCK):
            crc = zlib.crc32(blk, crc)
            h.update(blk)
    return crc & 0xFFFFFFFF, h.hexdigest()


def extract(rz, e, out, retries=4):
    dst = safe_target(out, e["name"])
    if os.path.exists(dst) and os.path.getsize(dst) == e["usize"]:
        crc, sha = file_crc_sha(dst)
        if crc == e["crc32"]:
            return dict(e, sha256=sha, skipped=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for attempt in range(retries):
        try:
            hdr = rz.read(e["lho"], 30)
            if hdr[:4] != b"PK\x03\x04":
                raise IOError(f"bad local header for {e['name']}")
            fnl, exl = struct.unpack("<HH", hdr[26:30])
            if e["method"] not in (0, 8):
                raise ValueError(f"unsupported compression method {e['method']} for {e['name']}")
            dec = zlib.decompressobj(-15) if e["method"] == 8 else None
            crc, h, n, tmp = 0, hashlib.sha256(), 0, dst + ".part"
            with open(tmp, "wb") as f:
                for blk in rz.stream(e["lho"] + 30 + fnl + exl, e["csize"]) if e["csize"] else []:
                    data = dec.decompress(blk) if dec else blk
                    crc = zlib.crc32(data, crc); h.update(data); n += len(data); f.write(data)
                if dec:
                    data = dec.flush()
                    crc = zlib.crc32(data, crc); h.update(data); n += len(data); f.write(data)
            crc &= 0xFFFFFFFF
            if n != e["usize"] or crc != e["crc32"]:
                raise IOError(f"verify failed for {e['name']}: size {n}/{e['usize']} crc {crc:08x}/{e['crc32']:08x}")
            os.replace(tmp, dst)
            return dict(e, sha256=h.hexdigest(), skipped=False)
        except Exception as ex:  # noqa: BLE001 - retry any network/verify error
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1} for {e['name']}: {ex}", file=sys.stderr)
            time.sleep(2 ** attempt * 5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="URL prefix the chunk names are appended to")
    ap.add_argument("--chunks", required=True, help="comma-separated chunk/file names, in concatenation order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", default=None, help="regex; matching member names are skipped")
    ap.add_argument("--index-out", required=True, help="JSON listing of the zip and the extracted members")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    rz = ChunkedRemote(a.base, a.chunks.split(","))
    entries = central_directory(rz)
    excl = re.compile(a.exclude) if a.exclude else None
    files = [e for e in entries if not e["name"].endswith("/")]
    want = [e for e in files if not (excl and excl.search(e["name"]))]
    print(f"{a.chunks.split(',')[0]}...: {len(files)} files in zip, extracting {len(want)} "
          f"({sum(e['csize'] for e in want) / 1e9:.3f} GB compressed -> {sum(e['usize'] for e in want) / 1e9:.3f} GB)")

    done, t0 = [], time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(extract, rz, e, a.out): e for e in want}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result()
            done.append(r)
            if i % 25 == 0 or i == len(want):
                print(f"  {i}/{len(want)} files, {time.time() - t0:.0f}s", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.index_out)), exist_ok=True)
    with open(a.index_out, "w") as f:
        json.dump(dict(
            source_urls=rz.urls, chunk_sizes=rz.sizes, zip_total_bytes=rz.total,
            exclude_regex=a.exclude, zip_file_count=len(files),
            excluded=[dict(name=e["name"], csize=e["csize"], usize=e["usize"]) for e in files if e not in want],
            extracted=sorted(({k: v for k, v in r.items() if k not in ("lho", "skipped")} for r in done),
                             key=lambda r: r["name"]),
        ), f, indent=1)
    print(f"verified {len(done)} files ({sum(r['skipped'] for r in done)} already present); index -> {a.index_out}")


if __name__ == "__main__":
    main()
