"""Print the layout of a MATLAB v7.3 batch file (read-only) to confirm structure before extraction."""
import sys

import h5py
import numpy as np


def describe(f, obj, name, indent="  "):
    if isinstance(obj, h5py.Dataset):
        print(f"{indent}{name}: dataset shape={obj.shape} dtype={obj.dtype}")
    else:
        print(f"{indent}{name}: group keys={list(obj.keys())}")


def deref_desc(f, ref):
    obj = f[ref]
    if isinstance(obj, h5py.Dataset):
        mclass = obj.attrs.get("MATLAB_class", b"").decode() if "MATLAB_class" in obj.attrs else ""
        return f"shape={obj.shape} dtype={obj.dtype} matlab_class={mclass}"
    return f"group keys={list(obj.keys())}"


def main(path):
    with h5py.File(path, "r") as f:
        print(f"File: {path}")
        print(f"Top-level keys: {list(f.keys())}")
        batch = f["batch"]
        print("batch fields:")
        for k in batch.keys():
            describe(f, batch[k], k)
        n_cells = batch["summary"].shape[0]
        print(f"\nNumber of cells (rows of batch/summary): {n_cells}")

        print("\nCell 0, per-field contents:")
        for k in batch.keys():
            ref = batch[k][0, 0]
            print(f"  {k}: {deref_desc(f, ref)}")
            obj = f[ref]
            if isinstance(obj, h5py.Group):
                for sk in obj.keys():
                    d = obj[sk]
                    extra = ""
                    if isinstance(d, h5py.Dataset) and d.dtype == object:
                        extra = f" -> first element: {deref_desc(f, d[0, 0])}"
                    print(f"      {sk}: shape={d.shape} dtype={d.dtype}{extra}")
            elif obj.dtype == np.uint16:
                print(f"      as string: {''.join(chr(c) for c in obj[()].flatten())!r}")
            else:
                print(f"      value(s): {obj[()].flatten()[:5]}")


if __name__ == "__main__":
    main(sys.argv[1])
