import pytest

from linkengine import urn_to_text


@pytest.mark.parametrize(
    ("urn", "expected"),
    [
        (
            "urn:nir:presidente.repubblica:decreto:1973-09-29;600~art60",
            "art. 60 D.P.R. n. 600/1973",
        ),
        (
            "urn:nir:ministero.economia.e.finanze:decreto:2024-07-31;126~art3",
            "art. 3 decreto ministeriale n. 126/2024",
        ),
    ],
)
def test_urn_to_text_renders_full_date_nir_with_locator(urn, expected):
    assert urn_to_text(urn) == expected


def test_urn_to_text_keeps_year_only_nir_behavior():
    assert (
        urn_to_text("urn:nir:presidente.repubblica:decreto:1973;600~art60")
        == "art. 60 D.P.R. n. 600/1973"
    )
