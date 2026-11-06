# EX-IMO training and evaluation image: PyTorch (CUDA 12.8 wheels, so only the host NVIDIA driver is needed), no ROS.
#   docker/build.sh            builds ex-imo:latest
#   docker/run.sh <command>    runs it with the repo, data and outputs mounted
FROM python:3.10-slim

ARG TORCH_INDEX=https://download.pytorch.org/whl/cu128
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg

# wget and git are used by data_prep/fetch_datasets.sh.
RUN apt-get update && apt-get install -y --no-install-recommends wget git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
 && pip install --extra-index-url "$TORCH_INDEX" -r /tmp/requirements.txt \
 && pip freeze > /opt/pip-freeze.txt \
 && rm /tmp/requirements.txt

WORKDIR /workspace/EX-IMO
CMD ["bash"]
