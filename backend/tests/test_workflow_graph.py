"""Graph contracts independent of database, providers and runtime workers."""
import copy
import unittest

from app.services.workflow_graph import next_node, validate_graph


class WorkflowGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = {
            "nodes": [{"id": "start", "type": "start"},
                      {"id": "branch", "type": "condition"},
                      {"id": "yes", "type": "end"},
                      {"id": "no", "type": "end"}],
            "edges": [{"source": "start", "target": "branch"},
                      {"source": "branch", "target": "yes", "condition": "true"},
                      {"source": "branch", "target": "no", "condition": "default"}],
        }

    def test_branch_prefers_condition_to_default_and_preserves_input(self):
        original = copy.deepcopy(self.graph)
        graph = validate_graph(self.graph)
        self.assertEqual(next_node(graph, "branch", {"result": True}), "yes")
        self.assertEqual(next_node(graph, "branch", {"result": False}), "no")
        self.assertIsNone(next_node(graph, "yes", {}))
        self.assertEqual(self.graph, original)

    def test_missing_match_is_not_silent_success(self):
        self.graph["edges"][-1]["condition"] = "false"
        validate_graph(self.graph)
        self.graph["edges"].pop()
        with self.assertRaisesRegex(ValueError, "No outgoing condition matched"):
            next_node(self.graph, "branch", {"result": False})

    def test_ambiguous_branch_and_cycle_rejected(self):
        self.graph["edges"][-1]["condition"] = "true"
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            validate_graph(self.graph)
        self.graph["edges"][-1] = {"source": "branch", "target": "start"}
        with self.assertRaises(ValueError):
            validate_graph(self.graph)

    def test_malformed_nodes_edges_and_config_are_validation_errors(self):
        bad = [None, [], {"nodes": [None, {}], "edges": []}]
        for field, value in [("edges", [None]), ("nodes", ["start", "end"])]:
            bad.append({**self.graph, field: value})
        graph = copy.deepcopy(self.graph)
        graph["nodes"][1]["config"] = None
        bad.append(graph)
        for area, key, value in [("nodes", "type", []), ("edges", "source", []),
                                 ("edges", "target", {}), ("edges", "condition", ["true"])]:
            graph = copy.deepcopy(self.graph)
            graph[area][0][key] = value
            bad.append(graph)
        for graph in bad:
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                validate_graph(graph)

    def test_old_runtime_imports_remain_compatible(self):
        from app.services import orchestration
        self.assertIs(orchestration.validate_graph, validate_graph)
        self.assertIs(orchestration.next_node, next_node)
