"""The contract gate must detect fields, requiredness and security drift."""
import copy
import unittest
from scripts.api_contract_check import contract


class ContractGateTests(unittest.TestCase):
    def test_structural_changes_are_detected_but_prose_is_not(self):
        schema = {"paths": {"/test": {"post": {"operationId": "test", "parameters": [{"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Result"}}}}}, "security": [{"HTTPBearer": []}]}}}, "components": {"schemas": {"Result": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}}
        baseline = contract(schema)
        prose = copy.deepcopy(schema)
        prose["paths"]["/test"]["post"]["responses"]["200"]["description"] = "New wording"
        self.assertEqual(baseline, contract(prose))
        for mutation in ("type", "required", "security"):
            changed = copy.deepcopy(schema)
            if mutation == "type": changed["components"]["schemas"]["Result"]["properties"]["value"]["type"] = "integer"
            elif mutation == "required": changed["paths"]["/test"]["post"]["parameters"][0]["required"] = False
            else: changed["paths"]["/test"]["post"]["security"] = []
            self.assertNotEqual(baseline, contract(changed))
