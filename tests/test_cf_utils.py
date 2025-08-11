import pytest

from batch.utils.cf_utils import CFModel


def test_cfmodel_build_and_scores():
    interactions = {
        "u1": ["i1", "i2"],
        "u2": ["i1", "i2"],
        "u3": ["i1"],
    }

    model = CFModel()
    model.build(interactions)

    assert model.is_ready
    assert "i1" in model.similarity_matrix.index
    assert "i2" in model.similarity_matrix.columns

    expected_sim = 2 / 3
    assert model.similarity_matrix.loc["i1", "i2"] == pytest.approx(expected_sim)

    scores = model.get_scores(["i1"], {"i2", "i3"})
    assert scores["i2"] == pytest.approx(expected_sim)
    assert "i3" not in scores

