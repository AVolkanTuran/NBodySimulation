"""Replay trajectories produced by the C++ N-body simulator."""

import argparse
import csv
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pygame

SOLAR_NAMES = ("Sun", "Mercury", "Venus", "Earth", "Mars",
               "Jupiter", "Saturn", "Uranus", "Neptune")
SOLAR_COLORS = (
    (255, 215, 90), (190, 185, 175), (235, 190, 120), (90, 165, 255),
    (235, 110, 75), (220, 180, 145), (230, 210, 155), (130, 225, 225),
    (95, 135, 255),
)


@dataclass(frozen=True)
class Particle:
    id: int
    mass: float
    x: float
    y: float


@dataclass(frozen=True)
class Frame:
    step: int
    time: float
    particles: tuple[Particle, ...]


def load_trajectory(path: Path) -> list[Frame]:
    frames: list[Frame] = []
    particles: dict[int, Particle] = {}
    step = -1
    time = 0.0
    expected_masses: dict[int, float] | None = None

    def finish_frame() -> None:
        nonlocal expected_masses
        masses = {particle.id: particle.mass for particle in particles.values()}
        if expected_masses is None:
            expected_masses = masses
        elif masses != expected_masses:
            raise ValueError(f"Step {step}: particle IDs or masses changed")
        frames.append(Frame(step, time, tuple(particles[key] for key in sorted(particles))))

    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["step", "time", "id", "mass", "x", "y"]:
            raise ValueError("Expected CSV header: step,time,id,mass,x,y")
        for line, row in enumerate(reader, start=2):
            try:
                row_step = int(row["step"])
                row_time = float(row["time"])
                particle = Particle(
                    int(row["id"]), float(row["mass"]), float(row["x"]), float(row["y"])
                )
                if None in row or not all(
                    math.isfinite(value)
                    for value in (row_time, particle.mass, particle.x, particle.y)
                ):
                    raise ValueError("extra columns or non-finite values")
                if row_step < 0 or row_time < 0 or particle.id < 0 or particle.mass <= 0:
                    raise ValueError("negative step/time/ID or non-positive mass")
            except (ValueError, TypeError) as error:
                raise ValueError(f"Line {line}: invalid trajectory row ({error})") from error
            if row_step != step:
                if particles:
                    finish_frame()
                    if row_step <= step or row_time <= time:
                        raise ValueError(f"Line {line}: frames must increase in step and time")
                particles = {}
                step, time = row_step, row_time
            elif row_time != time:
                raise ValueError(f"Line {line}: inconsistent time within step {step}")
            if particle.id in particles:
                raise ValueError(f"Line {line}: duplicate particle ID {particle.id}")
            particles[particle.id] = particle
    if not particles:
        raise ValueError("Trajectory contains no particles")
    finish_frame()
    return frames


class Viewer:
    def __init__(self, frames: list[Frame], size: tuple[int, int], speed: float,
                 solar_system: bool = False):
        self.frames = frames
        self.size = size
        self.speed = speed
        self.index = 0
        self.play_time = frames[0].time
        self.paused = False
        self.show_trails = True
        self.auto_fit = True
        self.center = (0.0, 0.0)
        self.scale = 1.0
        self.trails: dict[int, deque[tuple[float, float]]] = {}
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.solar_system = solar_system
        self.labels = [
            self.small_font.render(name, True, color)
            for name, color in zip(SOLAR_NAMES, SOLAR_COLORS)
        ] if solar_system else []
        self.record_trails()
        self.fit()

    def fit(self) -> None:
        particles = self.frames[self.index].particles
        xmin, xmax = min(p.x for p in particles), max(p.x for p in particles)
        ymin, ymax = min(p.y for p in particles), max(p.y for p in particles)
        self.center = (xmin / 2 + xmax / 2, ymin / 2 + ymax / 2)
        width, height = self.size
        self.scale = min((width - 80) / max(xmax - xmin, 0.1),
                         (height - 180) / max(ymax - ymin, 0.1))
        self.scale = max(1e-9, min(1e9, self.scale))

    def screen_position(self, x: float, y: float) -> tuple[int, int]:
        width, height = self.size
        sx = width / 2 + (x - self.center[0]) * self.scale
        sy = (height + 90) / 2 - (y - self.center[1]) * self.scale
        # Bound off-screen coordinates before handing them to SDL's integer drawing API.
        return (round(max(-1_000_000, min(1_000_000, sx))),
                round(max(-1_000_000, min(1_000_000, sy))))

    def zoom(self, factor: float, position: tuple[int, int]) -> None:
        self.auto_fit = False
        old_scale = self.scale
        self.scale = max(1e-9, min(1e9, self.scale * factor))
        dx = position[0] - self.size[0] / 2
        dy = position[1] - (self.size[1] + 90) / 2
        self.center = (self.center[0] + dx / old_scale - dx / self.scale,
                       self.center[1] - dy / old_scale + dy / self.scale)

    def pan(self, relative: tuple[int, int]) -> None:
        self.auto_fit = False
        self.center = (self.center[0] - relative[0] / self.scale,
                       self.center[1] + relative[1] / self.scale)

    def record_trails(self) -> None:
        for particle in self.frames[self.index].particles:
            self.trails.setdefault(particle.id, deque(maxlen=80)).append(
                (particle.x, particle.y)
            )

    def restart(self) -> None:
        self.index = 0
        self.play_time = self.frames[0].time
        self.trails.clear()
        self.record_trails()
        self.auto_fit = True
        self.fit()

    def step_forward(self) -> None:
        if self.index < len(self.frames) - 1:
            self.index += 1
            self.record_trails()
        self.play_time = self.frames[self.index].time
        if self.auto_fit:
            self.fit()

    def update(self, elapsed: float) -> None:
        if self.paused:
            return
        previous_index = self.index
        self.play_time = min(self.frames[-1].time, self.play_time + elapsed * self.speed)
        while (self.index + 1 < len(self.frames)
               and self.frames[self.index + 1].time <= self.play_time):
            self.index += 1
            self.record_trails()
        if self.auto_fit and self.index != previous_index:
            self.fit()

    def color(self, particle_id: int) -> tuple[int, int, int]:
        if self.solar_system:
            return SOLAR_COLORS[particle_id]
        color = pygame.Color(0)
        color.hsva = ((particle_id * 137.508) % 360, 55, 100, 100)
        return color.r, color.g, color.b

    def draw(self, surface: pygame.Surface, fps: float) -> None:
        surface.fill((8, 12, 24))
        width, height = self.size
        surface.set_clip(pygame.Rect(0, 90, width, height - 120))
        if self.show_trails:
            for particle_id, trail in self.trails.items():
                if len(trail) > 1:
                    color = tuple(channel // 3 for channel in self.color(particle_id))
                    pygame.draw.lines(surface, color, False,
                                      [self.screen_position(x, y) for x, y in trail])
        for particle in self.frames[self.index].particles:
            position = self.screen_position(particle.x, particle.y)
            if surface.get_clip().collidepoint(position):
                radius = (7 if particle.id == 0 else 4) if self.solar_system else \
                    max(2, min(8, round(math.sqrt(particle.mass))))
                pygame.draw.circle(surface, self.color(particle.id), position, radius)
                pygame.draw.circle(surface, (235, 245, 255), position, 1)
                if self.solar_system:
                    surface.blit(self.labels[particle.id], (position[0] + 8, position[1] - 8))
        surface.set_clip(None)
        pygame.draw.rect(surface, (17, 25, 43), (0, 0, width, 90))
        frame = self.frames[self.index]
        state = "PAUSED" if self.paused else (
            "FINISHED" if self.index == len(self.frames) - 1 else "PLAYING"
        )
        surface.blit(self.font.render("N-BODY / TRAJECTORY VIEWER", True, (125, 210, 255)),
                     (20, 14))
        status = (f"{state}   |   {len(frame.particles)} bodies   |   step {frame.step}"
                  f"   |   t = {frame.time:.3f}   |   {self.speed:g}x   |   {fps:.0f} FPS")
        surface.blit(self.small_font.render(status, True, (205, 216, 235)), (20, 44))
        controls = ("Space: pause   Right: step   R: restart   T: trails"
                    "   F: auto-fit   +/-: speed")
        surface.blit(self.small_font.render(controls, True, (145, 162, 190)), (20, 68))
        footer = "Wheel: zoom at cursor   |   Left-drag: pan   |   Esc: quit"
        surface.blit(self.small_font.render(footer, True, (145, 162, 190)),
                     (20, height - 24))
        progress = self.index / max(1, len(self.frames) - 1)
        pygame.draw.rect(surface, (37, 51, 74), (0, height - 32, width, 3))
        pygame.draw.rect(surface, (125, 210, 255), (0, height - 32, int(width * progress), 3))


def positive_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Must be a finite positive number")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path, nargs="?", default=Path("trajectory.csv"))
    parser.add_argument("--speed", type=positive_float, default=1.0,
                        help="Simulation time units per wall-clock second (default: 1)")
    parser.add_argument("--solar-system", action="store_true",
                        help="Label and color IDs from the solar-system preset")
    args = parser.parse_args()
    try:
        frames = load_trajectory(args.trajectory)
        if args.solar_system and [p.id for p in frames[0].particles] != list(range(9)):
            raise ValueError("Solar-system labels require particle IDs 0 through 8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")

    pygame.init()
    try:
        surface = pygame.display.set_mode((1100, 750), pygame.RESIZABLE)
        pygame.display.set_caption("N-body simulation")
        viewer = Viewer(frames, surface.get_size(), args.speed, args.solar_system)
        clock = pygame.time.Clock()
        running = True
        while running:
            elapsed = clock.tick(60) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    surface = pygame.display.set_mode(
                        (max(800, event.w), max(400, event.h)), pygame.RESIZABLE
                    )
                    viewer.size = surface.get_size()
                    if viewer.auto_fit:
                        viewer.fit()
                elif event.type == pygame.MOUSEWHEEL:
                    viewer.zoom(1.2 ** max(-20, min(20, event.y)), pygame.mouse.get_pos())
                elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                    viewer.pan(event.rel)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        viewer.paused = not viewer.paused
                    elif event.key == pygame.K_RIGHT:
                        viewer.paused = True
                        viewer.step_forward()
                    elif event.key == pygame.K_r:
                        viewer.restart()
                    elif event.key == pygame.K_t:
                        viewer.show_trails = not viewer.show_trails
                    elif event.key == pygame.K_f:
                        viewer.auto_fit = True
                        viewer.fit()
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        viewer.speed = min(1024.0, viewer.speed * 2)
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        viewer.speed = max(1 / 1024, viewer.speed / 2)
            viewer.update(elapsed)
            viewer.draw(surface, clock.get_fps())
            pygame.display.flip()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
