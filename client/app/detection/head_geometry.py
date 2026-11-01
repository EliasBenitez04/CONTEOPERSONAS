"""Geometria aproximada de cabeza desde un bbox de persona YOLO.

No es un detector de cabezas independiente: el tracker sigue identificando
personas completas, y el conteo usa una referencia consistente arriba del bbox.
"""


def estimate_head_geometry(x1, y1, x2, y2, frame_width, frame_height):
    """Retorna (cuadro_cabeza, punto_superior), ambos limitados al fotograma."""
    frame_width = max(1, int(frame_width))
    frame_height = max(1, int(frame_height))
    left = max(0, min(frame_width - 1, int(x1)))
    top = max(0, min(frame_height - 1, int(y1)))
    right = max(left, min(frame_width - 1, int(x2)))
    bottom = max(top, min(frame_height - 1, int(y2)))
    width = max(1, right - left)
    height = max(1, bottom - top)

    head_x1 = max(0, min(frame_width - 1, round(left + width * 0.30)))
    head_x2 = max(head_x1, min(frame_width - 1, round(left + width * 0.70)))
    head_y1 = max(0, min(frame_height - 1, round(top + height * 0.02)))
    head_y2 = max(head_y1, min(frame_height - 1, round(top + height * 0.25)))

    point_x = int(round((head_x1 + head_x2) / 2))
    point_y = max(0, head_y1 - 6)
    return (
        (int(head_x1), int(head_y1), int(head_x2), int(head_y2)),
        (point_x, point_y)
    )
