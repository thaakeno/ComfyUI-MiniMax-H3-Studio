from h3studio.nodes.comparison import comparison_layout


def test_comparison_layout_keeps_references_left_and_result_large_on_right() -> None:
    layout = comparison_layout(3)

    assert layout["canvas"] == (1600, 1000)
    assert layout["references"][2] < layout["result"][0]
    assert layout["result"][2] - layout["result"][0] > 2 * (
        layout["references"][2] - layout["references"][0]
    )
    assert layout["cell_height"] >= 76
