from h3studio.nodes.model_setup import H3StudioModelSetup


def test_model_setup_is_ui_only_node():
    assert H3StudioModelSetup.CATEGORY == "H3 Studio"
    assert H3StudioModelSetup.RETURN_TYPES == ()
    assert H3StudioModelSetup.INPUT_TYPES() == {"required": {}}
    assert H3StudioModelSetup().noop() == ()
