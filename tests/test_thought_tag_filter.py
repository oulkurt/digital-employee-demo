from src.services.agent_sync import ThoughtTagFilter


def test_thought_tag_filter_strips_think_across_chunks():
    f = ThoughtTagFilter()
    assert f.feed("你好<think>内部") == "你好"
    assert f.feed("思考</think>世界") == "世界"


def test_thought_tag_filter_strips_analysis_and_stray_close():
    f = ThoughtTagFilter()
    assert f.feed("</think>你好") == "你好"
    assert f.feed("a<analysis>hidden</analysis>b") == "ab"


def test_final_answer_filter_only_emits_final():
    from src.services.agent_sync import FinalAnswerFilter

    f = FinalAnswerFilter()
    assert f.feed("前置<think>不该展示</think>") == ""
    assert f.feed("<final>你好") == "你好"
    assert f.feed("世界</final>尾巴") == "世界"
    # After </final>, ignore anything else
    assert f.feed("后续") == ""
