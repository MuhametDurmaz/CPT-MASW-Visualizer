"""Render a full camera orbit without modifying the interactive figure."""
import io
import math


def camera_eye(frame, frames, radius=1.8, height=0.9):
    angle = 2 * math.pi * frame / frames
    return dict(x=radius * math.cos(angle), y=radius * math.sin(angle), z=height)


def rotating_gif(figure, frames=60, seconds=6, width=800, height=600, progress=None):
    import plotly.graph_objects as go
    import plotly.io as pio
    from PIL import Image

    if frames < 2 or seconds <= 0:
        raise ValueError("Use at least two frames and a positive duration.")
    export = go.Figure(figure)
    export.update_layout(width=width, height=height, paper_bgcolor="white")
    images = []
    try:
        for frame in range(frames):
            export.update_layout(scene_camera=dict(eye=camera_eye(frame, frames),
                center=dict(x=0, y=0, z=0), up=dict(x=0, y=0, z=1)))
            png = pio.to_image(export, format="png", width=width, height=height, scale=1)
            with Image.open(io.BytesIO(png)) as source:
                images.append(source.convert("RGB"))
            if progress:
                progress((frame + 1) / frames)
        # A shared palette prevents colors from flickering between frames.
        palette = images[0].quantize(colors=256)
        encoded = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
        output = io.BytesIO()
        try:
            encoded[0].save(output, format="GIF", save_all=True, append_images=encoded[1:],
                duration=max(10, round(seconds * 1000 / frames / 10) * 10),
                loop=0, optimize=False, disposal=2)
            return output.getvalue()
        finally:
            palette.close()
            for image in encoded:
                image.close()
    finally:
        for image in images:
            image.close()
