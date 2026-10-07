from difflib import unified_diff


def diff_contexts(before: list[str], after: list[str]) -> str:
    return "\n".join(
        unified_diff(
            "\n".join(before).splitlines(),
            "\n".join(after).splitlines(),
            fromfile="base contexts",
            tofile="head contexts",
            lineterm="",
        )
    )
