from enum import Enum
import numpy as np
from scipy.interpolate import RectBivariateSpline

class HeatmapInterpolationMethod(Enum):
    LINEAR = 'linear'
    CUBIC = 'cubic'
    QUINTIC = 'quintic'

class HeatmapConverter:
    def __init__(self):
        pass

    def _resize_with_interpolation(self, origin: np.ndarray, shape: tuple, method: HeatmapInterpolationMethod) -> np.ndarray:
        if origin.ndim != 2:
            raise ValueError("origin must be a 2D numpy array")

        target_rows, target_cols = int(shape[0]), int(shape[1])
        current_rows, current_cols = origin.shape

        if target_rows <= 0 or target_cols <= 0:
            raise ValueError("target shape must be positive integers")

        # No resize needed
        if current_rows == target_rows and current_cols == target_cols:
            return origin

        # Determine spline order based on method
        if method == HeatmapInterpolationMethod.LINEAR:
            order = 1
        elif method == HeatmapInterpolationMethod.CUBIC:
            order = 3
        else:  # QUINTIC
            order = 5

        # RectBivariateSpline requires at least 2 points on each axis and
        # nx >= kx+1, ny >= ky+1 with kx,ky in [1,5].
        can_use_spline = current_rows >= 2 and current_cols >= 2

        if can_use_spline:
            kx = min(order, max(1, current_cols - 1))
            ky = min(order, max(1, current_rows - 1))

            # Original and target coordinate grids (normalized 0..1)
            x_orig = np.linspace(0, 1, current_cols)
            y_orig = np.linspace(0, 1, current_rows)
            x_new = np.linspace(0, 1, target_cols)
            y_new = np.linspace(0, 1, target_rows)

            spline = RectBivariateSpline(y_orig, x_orig, origin, kx=kx, ky=ky)
            resized = spline(y_new, x_new)
            return np.asarray(resized)

        # Fallback path for degenerate dimensions (when one of dims == 1)
        result = origin
        # Resize columns if needed
        if current_cols != target_cols:
            if current_cols == 1:
                result = np.repeat(result, target_cols, axis=1)
            else:
                x_old = np.linspace(0, 1, result.shape[1])
                x_new = np.linspace(0, 1, target_cols)
                result = np.vstack([np.interp(x_new, x_old, row) for row in result])

        # Resize rows if needed
        if result.shape[0] != target_rows:
            if result.shape[0] == 1:
                result = np.repeat(result, target_rows, axis=0)
            else:
                y_old = np.linspace(0, 1, result.shape[0])
                y_new = np.linspace(0, 1, target_rows)
                # Interpolate along columns independently and stack back
                result = np.vstack([
                    np.interp(y_new, y_old, result[:, j]) for j in range(result.shape[1])
                ]).T

        return result

    def _merge(self, array1: np.ndarray, array2: np.ndarray) -> np.ndarray:
        if array1.ndim != 2 or array2.ndim != 2:
            raise ValueError("Both arrays must be 2D to merge")
        if array1.shape[1] != array2.shape[1]:
            raise ValueError(
                f"Cannot merge arrays with different column sizes: {array1.shape[1]} != {array2.shape[1]}"
            )
        return np.concatenate((array1, array2), axis=0)

    # Body와 Head 데이터를 합쳐서 하나의 Heatmap으로 변환
    def convert(self, head: np.ndarray, body: np.ndarray, method: HeatmapInterpolationMethod = HeatmapInterpolationMethod.LINEAR) -> np.ndarray:
        if head.ndim != 2 or body.ndim != 2:
            raise ValueError("head and body must be 2D numpy arrays")

        head_rows, head_cols = head.shape
        body_rows, body_cols = body.shape

        target_cols = max(head_cols, body_cols)

        # Resize columns to match target, keep original row counts
        head_resized = self._resize_with_interpolation(head, (head_rows, target_cols), method) \
            if head_cols != target_cols else head
        body_resized = self._resize_with_interpolation(body, (body_rows, target_cols), method) \
            if body_cols != target_cols else body

        merged = self._merge(head_resized, body_resized)

        # merged shape should be (head_rows + body_rows, target_cols)
        return merged
