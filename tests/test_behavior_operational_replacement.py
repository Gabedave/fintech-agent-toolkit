import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_behavior


class BehaviorOperationalReplacement(unittest.TestCase):
    def test_nonzero_exit_with_valid_structured_output_is_not_replaceable(self):
        scenario = {"id": "synthetic", "prompt": "Classify this request."}
        usable = {"playbook": "unexpected-but-usable"}

        def write_result(command, _input_text, _timeout_seconds):
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps(usable))
            return 1, "", "late CLI failure"

        with mock.patch.object(
            evaluate_behavior, "run_command", side_effect=write_result
        ) as run_command:
            result = evaluate_behavior.run_scenario(
                Path("/synthetic"), scenario, None, 60
            )

        self.assertEqual(result, usable)
        run_command.assert_called_once()

    def test_nonzero_exit_without_structured_output_is_replaceable(self):
        scenario = {"id": "synthetic", "prompt": "Classify this request."}
        with mock.patch.object(
            evaluate_behavior,
            "run_command",
            return_value=(1, "", "CLI failed before output"),
        ):
            with self.assertRaises(evaluate_behavior.BehaviorEvaluationError) as failure:
                evaluate_behavior.run_scenario(Path("/synthetic"), scenario, None, 60)

        self.assertIn("Codex smoke run failed (1)", str(failure.exception))
        self.assertIn("cannot read structured result", str(failure.exception))

    def test_timeout_with_valid_structured_output_is_not_replaceable(self):
        scenario = {"id": "synthetic", "prompt": "Classify this request."}
        usable = {"playbook": "unexpected-but-usable"}

        def write_result_then_timeout(command, _input_text, _timeout_seconds):
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps(usable))
            raise evaluate_behavior.BehaviorTimeout

        with mock.patch.object(
            evaluate_behavior, "run_command", side_effect=write_result_then_timeout
        ) as run_command:
            result = evaluate_behavior.run_scenario(
                Path("/synthetic"), scenario, None, 60
            )

        self.assertEqual(result, usable)
        run_command.assert_called_once()

    def test_one_operational_replacement_can_supply_a_usable_result(self):
        scenario = {"id": "synthetic"}
        usable = {"playbook": "fintech-mode"}
        with mock.patch.object(
            evaluate_behavior,
            "run_scenario",
            side_effect=[
                evaluate_behavior.BehaviorEvaluationError("first result missing"),
                usable,
            ],
        ) as run_scenario:
            result = evaluate_behavior.run_scenario_with_replacement(
                Path("/synthetic"),
                scenario,
                None,
                60,
                replacement_available=True,
            )

        self.assertEqual(result, (usable, 2, True, None))
        self.assertEqual(run_scenario.call_count, 2)

    def test_usable_result_is_never_retried_for_another_routing_decision(self):
        scenario = {"id": "synthetic"}
        usable = {"playbook": "unexpected-but-usable"}
        with mock.patch.object(
            evaluate_behavior, "run_scenario", return_value=usable
        ) as run_scenario:
            result = evaluate_behavior.run_scenario_with_replacement(
                Path("/synthetic"),
                scenario,
                None,
                60,
                replacement_available=True,
            )

        self.assertEqual(result, (usable, 1, False, None))
        run_scenario.assert_called_once()

    def test_failed_replacement_preserves_both_operational_errors(self):
        scenario = {"id": "synthetic"}
        with mock.patch.object(
            evaluate_behavior,
            "run_scenario",
            side_effect=[
                evaluate_behavior.BehaviorEvaluationError("first result missing"),
                evaluate_behavior.BehaviorEvaluationError("replacement timed out"),
            ],
        ):
            result = evaluate_behavior.run_scenario_with_replacement(
                Path("/synthetic"),
                scenario,
                None,
                60,
                replacement_available=True,
            )

        self.assertEqual(result[:3], (None, 2, True))
        self.assertIn("initial attempt failed: first result missing", str(result[3]))
        self.assertIn(
            "operational replacement failed: replacement timed out", str(result[3])
        )

    def test_coordinator_consumes_only_one_replacement_across_the_suite(self):
        scenarios = [{"id": "first"}, {"id": "second"}]
        outcomes = [
            evaluate_behavior.BehaviorEvaluationError("first result missing"),
            {"playbook": "usable"},
            evaluate_behavior.BehaviorEvaluationError("second result missing"),
        ]
        output = io.StringIO()
        with mock.patch.object(
            evaluate_behavior, "run_scenario", side_effect=outcomes
        ) as run_scenario, mock.patch.object(
            evaluate_behavior, "validate_result", return_value=[]
        ), mock.patch.object(
            evaluate_behavior, "routing_advisories", return_value=[]
        ), contextlib.redirect_stdout(output):
            result = evaluate_behavior.evaluate_scenarios(
                Path("/synthetic"), scenarios, None, 60
            )

        failures, advisories, replacements, usable_results = result
        self.assertEqual(run_scenario.call_count, 3)
        self.assertEqual(failures, ["second result missing"])
        self.assertEqual(advisories, [])
        self.assertEqual(replacements, 1)
        self.assertEqual(usable_results, 1)
        self.assertIn("first: evaluated (operational replacement used)", output.getvalue())
        self.assertIn("second: no usable result after 1 attempt(s)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
