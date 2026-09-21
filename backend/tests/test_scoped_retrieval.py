from app.core import GraphMindEngine


def test_query_can_scope_to_uploaded_document(tmp_path):
    engine = GraphMindEngine(tmp_path)
    first = engine.add_document("paper-a.txt", "The astronomy paper reports a redshift of 2.4.")
    second = engine.add_document("paper-b.txt", "The robotics paper reports a grasp success rate of 91 percent.")
    result = engine.ask("What success rate was reported?", document_id=second["id"])
    assert result["document_id"] == second["id"]
    assert result["evidence"][0]["document_name"] == "paper-b.txt"
    assert "robotics" in result["answer"].lower() or "91" in result["answer"]
