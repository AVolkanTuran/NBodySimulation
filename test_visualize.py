import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from visualize import Frame, Particle, Viewer, load_trajectory, main


class TrajectoryTests(unittest.TestCase):
    def load(self, contents: str) -> list[Frame]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.csv"
            path.write_text(contents, encoding="utf-8")
            return load_trajectory(path)

    def test_groups_frames_and_sorts_particle_ids(self):
        frames = self.load(
            "step,time,id,mass,x,y\n"
            "0,0,1,10,1,-1\n0,0,0,20,0,0\n"
            "5,0.005,0,20,0.1,0.2\n5,0.005,1,10,0.9,-0.8\n"
        )
        self.assertEqual([frame.step for frame in frames], [0, 5])
        self.assertEqual([particle.id for particle in frames[0].particles], [0, 1])
        self.assertEqual(frames[1].particles[1].y, -0.8)

    def test_rejects_malformed_or_inconsistent_trajectories(self):
        header = "step,time,id,mass,x,y\n"
        cases = [
            "", header, "x,y\n0,0\n",
            header + "0,0,0,10,nan,0\n",
            header + "0,0,0,10,0\n",
            header + "0,0,0,10,0,0,extra\n",
            header + "0,0,0,-10,0,0\n",
            header + "0,0,0,10,0,0\n0,0,0,10,1,1\n",
            header + "0,0,0,10,0,0\n0,1,1,10,1,1\n",
            header + "2,2,0,10,0,0\n1,1,0,10,1,1\n",
            header + "0,0,0,10,0,0\n1,0,0,10,1,1\n",
            header + "0,0,0,10,0,0\n0,0,1,10,1,1\n1,1,0,10,0,0\n",
            header + "0,0,0,10,0,0\n1,1,0,20,1,1\n",
        ]
        for contents in cases:
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.load(contents)


class ViewerTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.frames = [
            Frame(index, index * 0.5, (Particle(0, 10, index * 0.1, 0),))
            for index in range(100)
        ]
        self.viewer = Viewer(self.frames, (1100, 750), speed=2)

    def tearDown(self):
        pygame.quit()

    def test_timestamp_playback_pause_step_restart_and_bounded_trails(self):
        self.viewer.update(0.6)
        self.assertEqual(self.viewer.index, 2)
        self.viewer.paused = True
        self.viewer.update(100)
        self.assertEqual(self.viewer.index, 2)
        self.viewer.step_forward()
        self.assertEqual(self.viewer.index, 3)
        self.assertEqual(self.viewer.play_time, 1.5)
        self.viewer.paused = False
        self.viewer.update(100)
        self.assertEqual(self.viewer.index, 99)
        self.assertEqual(len(self.viewer.trails[0]), 80)
        self.viewer.restart()
        self.assertEqual(self.viewer.index, 0)
        self.assertEqual(self.viewer.play_time, 0)
        self.assertEqual(len(self.viewer.trails[0]), 1)

    def test_rendering_zoom_anchor_and_pan(self):
        surface = pygame.Surface(self.viewer.size)
        self.viewer.draw(surface, 60)
        position = self.viewer.screen_position(0, 0)
        self.assertEqual(surface.get_at(position)[:3], (235, 245, 255))
        self.viewer.zoom(2, position)
        self.assertFalse(self.viewer.auto_fit)
        self.assertEqual(self.viewer.screen_position(0, 0), position)
        self.viewer.pan((20, -10))
        self.assertEqual(self.viewer.screen_position(0, 0),
                         (position[0] + 20, position[1] - 10))

    def test_camera_follows_playback_until_manually_moved(self):
        self.viewer.update(1)
        self.assertEqual(self.viewer.center, (0.4, 0))
        self.viewer.pan((20, 0))
        center = self.viewer.center
        self.viewer.update(1)
        self.assertEqual(self.viewer.center, center)
        self.viewer.restart()
        self.assertTrue(self.viewer.auto_fit)
        self.assertEqual(self.viewer.center, (0, 0))

    def test_main_event_loop_renders_and_quits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.csv"
            path.write_text("step,time,id,mass,x,y\n0,0,0,10,0,0\n", encoding="utf-8")
            events = [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r),
                pygame.event.Event(pygame.VIDEORESIZE, w=900, h=600),
                pygame.event.Event(pygame.QUIT),
            ]
            with patch("sys.argv", ["visualize.py", str(path)]), \
                    patch("pygame.event.get", return_value=events), \
                    patch("pygame.display.flip", wraps=pygame.display.flip) as flip:
                main()
                flip.assert_called_once()

    def test_solar_labels_and_colors_render(self):
        frame = Frame(0, 0, tuple(Particle(i, 1, i, 0) for i in range(9)))
        viewer = Viewer([frame], (1100, 750), 1, solar_system=True)
        self.assertEqual(len(viewer.labels), 9)
        self.assertNotEqual(viewer.color(0), viewer.color(3))
        surface = pygame.Surface(viewer.size)
        viewer.draw(surface, 60)
        self.assertEqual(surface.get_at(viewer.screen_position(0, 0))[:3], (235, 245, 255))

    def test_solar_labels_reject_wrong_trajectory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.csv"
            path.write_text("step,time,id,mass,x,y\n0,0,0,10,0,0\n", encoding="utf-8")
            with patch("sys.argv", ["visualize.py", str(path), "--solar-system"]), \
                    self.assertRaises(SystemExit) as result:
                main()
            self.assertEqual(result.exception.code, 1)


ROOT = Path(__file__).resolve().parent
EXECUTABLE = next((path for path in (
    ROOT / "build" / "nbody_simulation.exe",
    ROOT / "build" / "Release" / "nbody_simulation.exe",
    ROOT / "build" / "nbody_simulation",
) if path.is_file()), None)


@unittest.skipUnless(EXECUTABLE, "Build the C++ simulator to run integration tests")
class SimulatorTests(unittest.TestCase):
    def test_export_sampling_final_frame_and_unchanged_console(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.csv"
            baseline = subprocess.run(
                [str(EXECUTABLE), "--steps", "12"], capture_output=True, text=True, check=True
            )
            exported = subprocess.run(
                [str(EXECUTABLE), "--steps", "12", "--sample-every", "5",
                 "--output", str(path)], capture_output=True, text=True, check=True
            )
            self.assertEqual(exported.stdout, baseline.stdout)
            default_path = Path(directory) / "explicit-default.csv"
            explicit = subprocess.run(
                [str(EXECUTABLE), "--preset", "default", "--steps", "12",
                 "--sample-every", "5", "--output", str(default_path)],
                capture_output=True, text=True, check=True
            )
            self.assertEqual(explicit.stdout, exported.stdout)
            self.assertEqual(default_path.read_bytes(), path.read_bytes())
            frames = load_trajectory(path)
            self.assertEqual([frame.step for frame in frames], [0, 5, 10, 12])
            self.assertEqual([frame.time for frame in frames], [0, 0.005, 0.01, 0.012])
            self.assertTrue(all(len(frame.particles) == 100 for frame in frames))
            self.assertEqual(frames[0].particles[1], Particle(1, 10, -0.01, -0.01))
            self.assertNotEqual(frames[0].particles, frames[-1].particles)

    def test_invalid_arguments_and_unwritable_output_fail_explicitly(self):
        for arguments in (
            ["--steps", "0"], ["--sample-every", "3bad"], ["--output"], ["--unknown"],
            ["--output", str(ROOT / "build")], ["--preset", "invalid"], ["--preset"],
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [str(EXECUTABLE), *arguments], capture_output=True, text=True
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error:", result.stderr)

    def test_solar_system_has_approximate_orbits_and_center_of_mass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solar.csv"
            subprocess.run(
                [str(EXECUTABLE), "--preset", "solar-system", "--steps", "6283",
                 "--sample-every", "100", "--output", str(path)],
                capture_output=True, text=True, check=True
            )
            frames = load_trajectory(path)
            self.assertTrue(all(len(frame.particles) == 9 for frame in frames))
            initial = frames[0].particles
            self.assertEqual([p.id for p in initial], list(range(9)))
            self.assertEqual(initial[0].mass, 1)
            self.assertAlmostEqual(initial[3].mass, 3.003e-6)
            self.assertAlmostEqual(sum(p.mass * p.x for p in initial), 0, places=14)
            self.assertAlmostEqual(sum(p.mass * p.y for p in initial), 0, places=14)
            final = frames[-1].particles
            self.assertAlmostEqual(sum(p.mass * p.x for p in final), 0, places=12)
            self.assertAlmostEqual(sum(p.mass * p.y for p in final), 0, places=12)
            for frame in frames:
                sun = frame.particles[0]
                for planet_id, expected_radius in ((1, 0.387), (3, 1.0), (5, 5.203)):
                    planet = frame.particles[planet_id]
                    radius = math.hypot(planet.x - sun.x, planet.y - sun.y)
                    self.assertLess(abs(radius - expected_radius), 0.02 * expected_radius)
            sun, earth = frames[-1].particles[0], frames[-1].particles[3]
            start_sun, start_earth = initial[0], initial[3]
            self.assertLess(math.hypot(
                (earth.x - sun.x) - (start_earth.x - start_sun.x),
                (earth.y - sun.y) - (start_earth.y - start_sun.y)
            ), 0.08)


if __name__ == "__main__":
    unittest.main()
