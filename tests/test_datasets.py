from pome.eval.datasets import TASKS, load_task


def test_banking77_has_all_77_labels_and_strata_are_gold_labels():
    t = load_task("banking77")
    assert len(t.items) == 300 and len(t.labels) == 77 and t.allow_oos
    assert t.strata == [i.label for i in t.items]


def test_clinc_maps_oos_rows_to_the_oos_label():
    t = load_task("clinc150")
    gold = [i.label for i in t.items]
    assert gold.count("out_of_scope") == 100 and len(t.labels) == 150
    assert "oos" not in t.labels and t.strata.count("oos") == 100


def test_massive_en_and_hi_share_item_ids_in_the_same_order():
    en, hi = load_task("massive_en"), load_task("massive_hi")
    assert [i.id for i in en.items] == [i.id for i in hi.items] and len(en.items) == 150
    assert not en.allow_oos and en.labels == hi.labels


def test_head_keeps_both_classes_for_clinc():
    t = load_task("clinc150", head=10)
    gold = [i.label for i in t.items]
    assert len(gold) == 10 and gold.count("out_of_scope") == 5


def test_task_names():
    assert set(TASKS) == {"banking77", "clinc150", "massive_en", "massive_hi"}
