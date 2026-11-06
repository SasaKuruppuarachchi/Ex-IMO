"""Held-out-shape folds: every flight is classified, and no held-out flight can reach training."""
import os

import pytest

from learning.data_management.prepare_datasets import public_uav_imo as C

NEEDS_DATA = pytest.mark.skipif(not os.path.isdir(os.path.join(C.WS, "data", "processed")), reason="needs the data mount")


@NEEDS_DATA
@pytest.mark.parametrize("dataset", sorted(C.FOLDS))
def test_every_flight_has_a_label(dataset):
    assert all(C.flight_label(dataset, n.rsplit(os.sep, 1)[0]) for n, _, _ in C.find_sequences(dataset))


@NEEDS_DATA
@pytest.mark.parametrize("dataset,fold", [(d, k) for d in sorted(C.FOLDS) for k in C.FOLDS[d]])
def test_fold_holds_out_some_but_not_all(dataset, fold):
    seqs = C.find_sequences(dataset)
    out = [n for n, _, _ in seqs if C.is_held_out(dataset, fold, n)]
    kept_train = [n for n, sp, _ in seqs if sp == "train" and not C.is_held_out(dataset, fold, n)]
    kept_val = [n for n, sp, _ in seqs if sp == "val" and not C.is_held_out(dataset, fold, n)]
    assert out and kept_train and kept_val


def test_no_fold_holds_out_nothing():
    assert not C.is_held_out("tii_ratm", None, "flight-01a-ellipse/train")
    assert C.is_held_out("tii_ratm", "ellipse", "flight-01a-ellipse/train")
    assert not C.is_held_out("tii_ratm", "ellipse", "flight-07a-lemniscate/train")
    assert C.is_held_out("nanobench", "round", "B5_helix_fast_rep1/test")
    assert not C.is_held_out("nanobench", "round", "B9_trefoil_fast_rep1/test")


def test_neurobem_label_uses_the_flight_comment():
    assert C.is_held_out("neurobem", "circles", "2021-02-03-13-43-38_seg_1/train")                 # wobbly circle
    assert not C.is_held_out("neurobem", "circles", "2021-02-03-16-10-37_seg_1/train")             # linear oscillation
    assert C.is_held_out("neurobem", "lemniscate_cpc", "2021-02-05-15-40-15_seg_1/train")          # cpc
