import re

with open("mortar_calc.py", "r") as f:
    code = f.read()

# Fix types to Sequence[float] to cover both lists and tuples
code = re.sub(
    r"def _sph_drag_coeff\(speed: float, _x: List\[int\] = SPH_GC_X, _y: List\[float\] = SPH_GC_Y, _lkp: Tuple\[int, \.\.\.\] = SPH_GC_LOOKUP, _i: Callable\[\[float\], int\] = int, _x0: float = float\(SPH_GC_X\[0\]\), _xl: float = float\(SPH_GC_X\[-1\]\), _y0: float = float\(SPH_GC_Y\[0\]\), _yl: float = float\(SPH_GC_Y\[-1\]\)\) -> float:",
    r"def _sph_drag_coeff(speed: float, _x: Sequence[float] = SPH_GC_X, _y: Sequence[float] = SPH_GC_Y, _lkp: Tuple[int, ...] = SPH_GC_LOOKUP, _i: Callable[[float], int] = int, _x0: float = float(SPH_GC_X[0]), _xl: float = float(SPH_GC_X[-1]), _y0: float = float(SPH_GC_Y[0]), _yl: float = float(SPH_GC_Y[-1])) -> float:",
    code
)

if "from typing import Dict, List, Optional, Tuple, Any, Callable" in code:
    code = code.replace(
        "from typing import Dict, List, Optional, Tuple, Any, Callable",
        "from typing import Dict, List, Optional, Tuple, Any, Callable, Sequence"
    )

with open("mortar_calc.py", "w") as f:
    f.write(code)
