"""Geometry and measured-pose acceptance for the first rigid UR5 insertion task."""

from dataclasses import asdict, dataclass
from math import acos, cos, degrees, hypot, isfinite, pi, sin, sqrt


@dataclass(frozen=True)
class TaskSpec:
    peg_radius_m: float = 0.004
    shaft_length_m: float = 0.060
    adapter_radius_m: float = 0.012
    adapter_length_m: float = 0.012
    hole_radius_m: float = 0.00475
    fixture_outer_radius_m: float = 0.030
    hole_depth_m: float = 0.025
    mesh_segments: int = 128
    approach_gap_m: float = 0.025
    insertion_depth_m: float = 0.020
    success_depth_m: float = 0.018
    radial_margin_m: float = 0.00010
    success_hold_steps: int = 10
    control_hz: int = 20
    physics_hz: int = 120

    @property
    def tip_offset_m(self):
        return self.adapter_length_m + self.shaft_length_m

    @property
    def effective_hole_radius_m(self):
        return self.hole_radius_m * cos(pi/self.mesh_segments)

    def metadata(self):
        return {**asdict(self), 'tip_offset_m': self.tip_offset_m,
                'effective_hole_radius_m': self.effective_hole_radius_m,
                'radial_clearance_m': self.effective_hole_radius_m-self.peg_radius_m}


def tool_mass_properties(spec=TaskSpec(), density_kg_m3=7800.0):
    """Two coaxial solid steel cylinders; origin at wrist mounting point."""
    cylinders = [(spec.adapter_radius_m, spec.adapter_length_m, spec.adapter_length_m/2),
                 (spec.peg_radius_m, spec.shaft_length_m, spec.adapter_length_m+spec.shaft_length_m/2)]
    parts = [(density_kg_m3*pi*r*r*h, r, h, z) for r,h,z in cylinders]
    mass = sum(m for m,_,_,_ in parts)
    center_z = sum(m*z for m,_,_,z in parts)/mass
    transverse = sum(m*(3*r*r+h*h)/12 + m*(z-center_z)**2 for m,r,h,z in parts)
    axial = sum(m*r*r/2 for m,r,_,_ in parts)
    return {'mass_kg':mass,'center_of_mass_tool_m':[0,0,center_z],
            'diagonal_inertia_kg_m2':[transverse,transverse,axial]}


def hole_top_position(offset_xy=(0.0,0.0),spec=TaskSpec()):
    if len(offset_xy)!=2 or not all(isfinite(value) for value in offset_xy) or hypot(*offset_xy)>.004:
        raise ValueError('Initial fixture offset must be finite and within 4 mm radially.')
    return [0.5498943328857422+offset_xy[0],0.10921555012464523+offset_xy[1],
            0.258075475692749-spec.tip_offset_m-spec.approach_gap_m]


def annulus_mesh(spec=TaskSpec()):
    """Closed manifold ring; all faces wound toward the outside of the solid."""
    n = spec.mesh_segments
    if n < 16 or not 0 < spec.hole_radius_m < spec.fixture_outer_radius_m or spec.hole_depth_m <= 0:
        raise ValueError('Invalid annulus dimensions.')
    vertices = []
    for radius,z in [(spec.hole_radius_m,0),(spec.fixture_outer_radius_m,0),
                     (spec.hole_radius_m,spec.hole_depth_m),(spec.fixture_outer_radius_m,spec.hole_depth_m)]:
        vertices.extend((radius*cos(2*pi*i/n),radius*sin(2*pi*i/n),z) for i in range(n))
    faces = []
    for i in range(n):
        j = (i+1)%n
        faces.extend([(2*n+i,3*n+i,3*n+j,2*n+j), (i,j,n+j,n+i),
                      (n+i,n+j,3*n+j,3*n+i), (i,2*n+i,2*n+j,j)])
    return vertices, faces


def rotate(quaternion, vector):
    w,x,y,z = quaternion
    vx,vy,vz = vector
    # q v q* for a unit wxyz quaternion.
    tx,ty,tz = 2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty, vy+w*ty+z*tx-x*tz, vz+w*tz+x*ty-y*tx]


def tcp_orientation_world(body_quaternion):
    """TCP +Z points toward wrist: q_tcp = q_body * RotX(pi).

    This places the downward insertion home TCP near identity, avoiding the
    rotation-vector discontinuity at +/-pi while preserving the physical shaft.
    """
    w,x,y,z=body_quaternion
    return [-x,w,z,-y]


def insertion_metrics(tip_position_world, tool_orientation_world, hole_top_world, spec=TaskSpec()):
    """Use measured tool tip and shaft direction, never commanded targets."""
    x,y = tip_position_world[0]-hole_top_world[0], tip_position_world[1]-hole_top_world[1]
    depth = hole_top_world[2]-tip_position_world[2]
    down = rotate(tool_orientation_world,[0,0,1])
    cosine = max(-1.0,min(1.0,-down[2]))
    tilt = degrees(acos(cosine))
    entry_offset = hypot(x,y)
    if depth > 0 and cosine > 1e-6:
        # Follow the shaft upwards from its tip to the plane of the hole mouth.
        entry_offset = hypot(x-down[0]*depth/cosine,y-down[1]*depth/cosine)
    worst_center = max(hypot(x,y),entry_offset)
    occupied_radius = worst_center + spec.peg_radius_m/max(cosine,1e-6)
    within_bore = occupied_radius <= spec.effective_hole_radius_m-spec.radial_margin_m
    success = spec.success_depth_m <= depth <= spec.hole_depth_m and tilt <= 1.0 and within_bore
    return {'depth_m':depth,'tip_lateral_error_m':hypot(x,y),'entry_lateral_error_m':entry_offset,
            'axis_tilt_deg':tilt,'occupied_radius_m':occupied_radius,'within_bore':within_bore,
            'instant_success':success}


def tilt_quaternion(x_deg, y_deg):
    """Base-frame rotation vector components, in degrees (not Euler angles)."""
    if not all(isfinite(v) for v in (x_deg,y_deg)) or hypot(x_deg,y_deg)>4:
        raise ValueError('Initial tilt must be finite and at most 4 degrees in norm.')
    x,y=x_deg*pi/180,y_deg*pi/180
    angle=hypot(x,y)
    scale=sin(angle/2)/angle if angle else .5
    return [cos(angle/2),x*scale,y*scale,0.0]


def toward_identity(quaternion, fraction):
    """Shortest spherical interpolation from a unit wxyz pose to identity."""
    if len(quaternion)!=4 or not all(isfinite(v) for v in quaternion) or not 0<=fraction<=1:
        raise ValueError('Invalid interpolation input.')
    norm=sqrt(sum(v*v for v in quaternion))
    if abs(norm-1)>1e-3:
        raise ValueError('Expected a unit quaternion.')
    q=[v/norm for v in quaternion]
    if q[0]<0: q=[-v for v in q]
    half_angle=acos(max(-1,min(1,q[0])))
    if half_angle<1e-10: return [1.0,0.0,0.0,0.0]
    remaining=half_angle*(1-fraction)
    return [cos(remaining)]+[v*sin(remaining)/sin(half_angle) for v in q[1:]]


def expert_targets(start_tip, hole_top, scenario, spec=TaskSpec(), start_orientation=(1,0,0,0)):
    """Oracle geometric expert: align above fixture, descend slowly, dwell."""
    if scenario not in ('aligned','rim','filled'):
        raise ValueError('Unknown validation scenario.')
    # Negative rim control intentionally keeps an 8 mm lateral misalignment.
    target_xy = [hole_top[0]+(0.008 if scenario=='rim' else 0),hole_top[1]]
    above = target_xy + [hole_top[2]+spec.approach_gap_m]
    bottom = target_xy + [hole_top[2]-spec.insertion_depth_m]
    targets = []
    previous = list(start_tip)
    for destination,count,phase in [(above,30,'align'),(bottom,100,'insert'),(bottom,20,'dwell')]:
        for i in range(1,count+1):
            orientation=toward_identity(start_orientation,i/count) if phase=='align' else [1.0,0.0,0.0,0.0]
            targets.append({'position':[a+(b-a)*i/count for a,b in zip(previous,destination)],
                            'orientation':orientation,'phase':phase})
        previous = destination
    return targets
