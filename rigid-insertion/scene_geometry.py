"""Author a massive fixed peg tool and a genuinely open static hole in USD."""

from episode import quat_multiply, quaternion
from task_math import TaskSpec, annulus_mesh, hole_top_position, rotate, tool_mass_properties

# Measured from the validated, gravity-compensated UR5 starting configuration.
CALIBRATION_WRIST_Q = [-0.18178356581036187,-0.6831960415497119,0.6833407020296421,0.18232769663907344]
DOWN_Q = [0.0,1.0,0.0,0.0]


def build_geometry(stage, scenario, spec=TaskSpec(), fixture_offset_xy=(0.0,0.0)):
    from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdPhysics, UsdShade

    robot_path='/World/envs/env_0/Robot'
    wrist_path=robot_path+'/wrist_3_link'
    tool_path=robot_path+'/PegTool'
    wrist=stage.GetPrimAtPath(wrist_path)
    if not wrist.IsValid():
        raise RuntimeError(f'UR5 wrist prim is missing: {wrist_path}')
    cache=UsdGeom.XformCache()

    def pose(path):
        matrix=cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path))
        q=matrix.ExtractRotationQuat()
        return list(matrix.ExtractTranslation()),quaternion([q.GetReal(),*q.GetImaginary()])

    wrist_position,wrist_orientation=pose(wrist_path)
    root_position,root_orientation=pose(robot_path)
    root_inverse=[root_orientation[0],*[-x for x in root_orientation[1:]]]
    calibrated=quaternion(CALIBRATION_WRIST_Q)
    mount=quaternion(quat_multiply([calibrated[0],*[-x for x in calibrated[1:]]],DOWN_Q))
    body_orientation=quaternion(quat_multiply(root_inverse,quat_multiply(wrist_orientation,mount)))
    body_position=rotate(root_inverse,[a-b for a,b in zip(wrist_position,root_position)])

    material=UsdShade.Material.Define(stage,'/World/InsertionMaterial')
    physics_material=UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    physics_material.CreateStaticFrictionAttr(0.4)
    physics_material.CreateDynamicFrictionAttr(0.3)
    physics_material.CreateRestitutionAttr(0.0)

    def collider(prim):
        UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
        contact=PhysxSchema.PhysxCollisionAPI.Apply(prim)
        contact.CreateContactOffsetAttr(0.00005)
        contact.CreateRestOffsetAttr(0.0)
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,materialPurpose='physics')

    def cylinder(path,radius,height,z,color):
        shape=UsdGeom.Cylinder.Define(stage,path)
        shape.CreateRadiusAttr(radius)
        shape.CreateHeightAttr(height)
        shape.CreateAxisAttr('Z')
        shape.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        UsdGeom.Xformable(shape).AddTranslateOp().Set(Gf.Vec3d(0,0,z))
        collider(shape.GetPrim())
        return shape

    body=UsdGeom.Xform.Define(stage,tool_path)
    xform=UsdGeom.Xformable(body)
    xform.AddTranslateOp().Set(Gf.Vec3d(*body_position))
    xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Quatd(body_orientation[0],Gf.Vec3d(*body_orientation[1:])))
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim()).CreateRigidBodyEnabledAttr(True)
    PhysxSchema.PhysxRigidBodyAPI.Apply(body.GetPrim()).CreateDisableGravityAttr(False)
    mass=tool_mass_properties(spec)
    mass_api=UsdPhysics.MassAPI.Apply(body.GetPrim())
    mass_api.CreateMassAttr(mass['mass_kg'])
    mass_api.CreateCenterOfMassAttr(Gf.Vec3f(*mass['center_of_mass_tool_m']))
    mass_api.CreateDiagonalInertiaAttr(Gf.Vec3f(*mass['diagonal_inertia_kg_m2']))
    mass_api.CreatePrincipalAxesAttr(Gf.Quatf(1.0))
    PhysxSchema.PhysxContactReportAPI.Apply(body.GetPrim()).CreateThresholdAttr(0.0)
    cylinder(tool_path+'/Adapter',spec.adapter_radius_m,spec.adapter_length_m,spec.adapter_length_m/2,(0.32,0.34,0.38))
    cylinder(tool_path+'/Shaft',spec.peg_radius_m,spec.shaft_length_m,spec.adapter_length_m+spec.shaft_length_m/2,(0.95,0.62,0.12))
    joint=UsdPhysics.FixedJoint.Define(stage,robot_path+'/PegToolJoint')
    joint.CreateBody0Rel().SetTargets([Sdf.Path(wrist_path)])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(tool_path)])
    joint.CreateLocalPos0Attr(Gf.Vec3f(0,0,0))
    joint.CreateLocalRot0Attr(Gf.Quatf(mount[0],Gf.Vec3f(*mount[1:])))
    joint.CreateLocalPos1Attr(Gf.Vec3f(0,0,0))
    joint.CreateLocalRot1Attr(Gf.Quatf(1.0))
    joint.CreateCollisionEnabledAttr(False)

    # The fixture is fixed to world; its opening has no center vertices/cap.
    # Initial hole position is from the validated UR5 start, with a 25 mm gap.
    hole_top=hole_top_position(fixture_offset_xy,spec)
    fixture=UsdGeom.Xform.Define(stage,'/World/Fixture')
    UsdGeom.Xformable(fixture).AddTranslateOp().Set(Gf.Vec3d(hole_top[0],hole_top[1],hole_top[2]-spec.hole_depth_m))
    vertices,faces=annulus_mesh(spec)
    mesh=UsdGeom.Mesh.Define(stage,'/World/Fixture/Hole')
    mesh.CreatePointsAttr([Gf.Vec3f(*v) for v in vertices])
    mesh.CreateFaceVertexCountsAttr([len(f) for f in faces])
    mesh.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    mesh.CreateSubdivisionSchemeAttr('none')
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateDisplayColorAttr([Gf.Vec3f(.15,.40,.68)])
    collider(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr('none')
    if scenario=='filled':
        cylinder('/World/Fixture/Cap',spec.hole_radius_m,.002,spec.hole_depth_m-.001,(.75,.2,.2))

    # Static pedestal makes the fixture's mounting visible, leaving room below the hole.
    for ix,iy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        cube=UsdGeom.Cube.Define(stage,f'/World/Post_{ix+1}_{iy+1}')
        cube.CreateSizeAttr(1.0)
        cube.CreateDisplayColorAttr([Gf.Vec3f(.25,.27,.30)])
        xf=UsdGeom.Xformable(cube)
        height=hole_top[2]-spec.hole_depth_m
        xf.AddTranslateOp().Set(Gf.Vec3d(hole_top[0]+ix*.018,hole_top[1]+iy*.018,height/2))
        xf.AddScaleOp().Set(Gf.Vec3f(.008,.008,height))
        collider(cube.GetPrim())
    return {'tool_body':'PegTool','mount_quaternion_wxyz':mount,'mass_properties':mass,
            'hole_top_world_m':hole_top,'fixture_offset_xy_m':list(fixture_offset_xy),'hole_collider':'static_triangle_mesh',
            'contact_offset_m':.00005,'static_friction':.4,'dynamic_friction':.3}
