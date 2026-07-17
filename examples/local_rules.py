"""Example local rules file for [tool.plintus] local-rules.

Wiring (add to your pyproject.toml):

    [tool.plintus]
    local-rules = ["examples/local_rules.py"]
    select = ["X001"]          # enable the custom rule
    # workers = 1               # local-rules force single-process anyway

Then run:

    plintus check examples/sample_violations.py

Expected output (one X001 diagnostic on the TODO comment line).
"""

from plintus.api import Rule, RuleContext, Severity


class NoTodoComments(Rule):
    id = "X001"
    message = "TODO comments are not allowed"
    severity = Severity.HINT
    targets = ("comment",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            if "TODO" in node.text().upper():
                ctx.report(node, "Remove TODO or track it in an issue tracker")


def register():
    return [NoTodoComments()]
