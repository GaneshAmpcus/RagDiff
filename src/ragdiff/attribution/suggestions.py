from typing import Any


def suggest_causes(
    differences: dict[str, dict[str, Any]],
) -> list[str]:
    return [
        f"{metric} changed by {value['delta']:+.3f} between the compared variants."
        for metric, value in differences.items()
        if value["delta"] != 0
    ]
