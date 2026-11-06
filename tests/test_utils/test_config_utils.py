"""Reading dataset and variable references out of control-file models."""

from __future__ import annotations

from ClimateGraph.utils.config_utils import split_ref


class TestSplitRef:
    def test_a_bare_name_takes_the_default(self):
        assert split_ref("PM25", "STATIONS") == ("STATIONS", "PM25")

    def test_a_qualified_name_brings_its_own(self):
        assert split_ref("MODEL::PM25", "STATIONS") == ("MODEL", "PM25")

    def test_a_bare_name_with_no_default_resolves_to_nothing(self):
        assert split_ref("PM25") == (None, "PM25")

    def test_a_qualified_name_needs_no_default(self):
        assert split_ref("MODEL::PM25") == ("MODEL", "PM25")

    def test_only_the_first_separator_splits(self):
        # The dataset name is everything before the first "::".
        assert split_ref("MODEL::odd::name") == ("MODEL", "odd::name")
