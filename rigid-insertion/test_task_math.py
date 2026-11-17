import collections
from math import cos, pi, sin
import unittest

from task_math import TaskSpec, annulus_mesh, expert_targets, hole_top_position, insertion_metrics, rotate, tcp_orientation_world, tool_mass_properties,tilt_quaternion,toward_identity


class TaskGeometryTests(unittest.TestCase):
    def test_angle_is_corrected_above_hole_before_descent(self):
        initial=tilt_quaternion(3,0)
        targets=expert_targets([.55,.1,.185],[.55,.1,.16],'aligned',start_orientation=initial)
        halfway=targets[14]['orientation']
        self.assertAlmostEqual(halfway[0],cos(1.5*pi/360))
        self.assertAlmostEqual(halfway[1],sin(1.5*pi/360))
        self.assertEqual(targets[29]['orientation'],[1,0,0,0])
        self.assertAlmostEqual(targets[29]['position'][2],.185)
        self.assertTrue(all(t['orientation']==[1,0,0,0] for t in targets[30:]))
        self.assertEqual(toward_identity([-v for v in initial],.5),toward_identity(initial,.5))
        for values in [(4,4),(float('nan'),0)]:
            with self.assertRaises(ValueError): tilt_quaternion(*values)

    def test_ring_is_closed_manifold_and_does_not_cap_the_hole(self):
        spec = TaskSpec()
        vertices,faces = annulus_mesh(spec)
        edges = collections.Counter()
        for face in faces:
            for a,b in zip(face,face[1:]+face[:1]):
                edges[tuple(sorted((a,b)))]+=1
        self.assertTrue(all(count==2 for count in edges.values()))
        self.assertEqual(len(vertices)-len(edges)+len(faces),0)  # Annular solid has genus 1.
        for face in faces:
            center=[sum(vertices[i][axis] for i in face)/4 for axis in range(3)]
            self.assertGreaterEqual((center[0]**2+center[1]**2)**.5,spec.effective_hole_radius_m-1e-12)

    def test_success_requires_measured_depth_and_alignment(self):
        hole=[.5,.1,.16]
        down=[0,1,0,0]
        self.assertFalse(insertion_metrics([.5,.1,.18],down,hole)['instant_success'])
        self.assertTrue(insertion_metrics([.5,.1,.14],down,hole)['instant_success'])
        self.assertFalse(insertion_metrics([.508,.1,.14],down,hole)['instant_success'])
        self.assertFalse(insertion_metrics([.5,.1,.12],down,hole)['instant_success'])

    def test_tilted_shaft_is_checked_at_hole_entry_not_only_at_tip(self):
        angle=3*pi/180
        q=[0,cos(angle/2),0,sin(angle/2)]
        metrics=insertion_metrics([0,0,-.020],q,[0,0,0])
        self.assertGreater(metrics['entry_lateral_error_m'],.001)
        self.assertFalse(metrics['instant_success'])

    def test_tool_inertia_is_positive_and_accounts_for_mount_adapter(self):
        p=tool_mass_properties()
        self.assertGreater(p['mass_kg'],.05)
        self.assertLess(p['mass_kg'],.08)
        self.assertTrue(all(i>0 for i in p['diagonal_inertia_kg_m2']))
        self.assertGreater(p['center_of_mass_tool_m'][2],0)

    def test_starting_offsets_are_bounded_and_expert_uses_the_actual_fixture(self):
        default=hole_top_position()
        shifted=hole_top_position((.003,0))
        self.assertAlmostEqual(shifted[0]-default[0],.003)
        self.assertEqual(shifted[2],default[2])
        targets=expert_targets([default[0],default[1],default[2]+.025],shifted,'aligned')
        self.assertEqual(targets[-1]['position'][:2],shifted[:2])
        for value in [(.005,0),(float('nan'),0),(.004,.004)]:
            with self.assertRaises(ValueError): hole_top_position(value)

    def test_tcp_frame_is_near_identity_on_both_sides_of_downward_half_turn(self):
        for epsilon in [-1e-8,1e-8]:
            body=[epsilon,(1-epsilon*epsilon)**.5,0,0]
            tcp=tcp_orientation_world(body)
            self.assertGreater(abs(tcp[0]),.999999)
            self.assertAlmostEqual(rotate(body,[0,0,1])[2],-1.0)
            self.assertAlmostEqual(rotate(tcp,[0,0,1])[2],1.0)

    def test_expert_is_bounded_and_negative_control_keeps_rim_offset(self):
        spec=TaskSpec()
        hole=[.55,.1,.16]
        for scenario in ('aligned','rim','filled'):
            targets=expert_targets([.55,.1,.185],hole,scenario,spec)
            self.assertEqual(len(targets),150)
            points=[[.55,.1,.185]]+[row['position'] for row in targets]
            from math import dist
            self.assertLess(max(dist(a,b) for a,b in zip(points,points[1:])),.00051)
            self.assertAlmostEqual(targets[-1]['position'][0],.558 if scenario=='rim' else .55)


if __name__=='__main__':
    unittest.main()
