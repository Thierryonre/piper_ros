import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, TimerAction
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from launch.event_handlers import OnProcessExit

import xacro

import re
def remove_comments(text):
    pattern = r'<!--(.*?)-->'
    return re.sub(pattern, '', text, flags=re.DOTALL)

def generate_launch_description():
    robot_name_in_model = 'piper'
    package_name = 'piper_description'
    urdf_name = "piper_no_gripper_description_gazebo.xacro"

    pkg_share = FindPackageShare(package=package_name).find(package_name) 
    urdf_model_path = os.path.join(pkg_share, f'urdf/{urdf_name}')

    # Start Gazebo server
    # start_gazebo_cmd =  ExecuteProcess(
    #     cmd=['gazebo', '--verbose','-s', 'libgazebo_ros_init.so', '-s', 'libgazebo_ros_factory.so'],
    #     output='screen')
    start_gazebo_cmd = ExecuteProcess(
        cmd=[
            'ign', 'gazebo',
            # '--verbose',
            '-r',  # run immediately
            # '-s', 'libros_gz_sim.so'
            'empty.sdf'
            # '/usr/share/ignition/ignition-gazebo6/worlds/empty.sdf'
        ],
        output='screen'
    )


    # Because the urdf file contains the line $(find mybot), it needs to be compiled using xacro.
    xacro_file = urdf_model_path
    config_file_path = os.path.join(FindPackageShare(package="piper_gazebo").find("piper_gazebo") , f'config/ros2_no_gripper_controllers.yaml')
    doc = xacro.parse(open(xacro_file))
    xacro.process_doc(doc, mappings={'config_path': config_file_path})
    # params = {'robot_description': doc.toxml()}
    params = {'robot_description': remove_comments(doc.toxml())}

    # After the robot_state_publisher node is started, it will publish the robot_description topic, the content of which is the content of the model file urdf.
    # It will also subscribe to the /joint_states topic, retrieve joint data, and then publish it to the tf and tf_static topics.
    # Can the names of these nodes and topics be customized?
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'use_sim_time': True}, params, {"publish_frequency":15.0}],
        output='screen'
    )

    # Launch the robot, retrieve model content via the robot_description topic, and then generate the model in Gazebo.
    spawn_entity_cmd = Node(
        package='ros_gz_sim', 
        executable='create',
        arguments=['-entity', robot_name_in_model,  '-topic', 'robot_description'], output='screen')

    # When Gazbo loads the URDF, will it start a joint_states node according to the URDF's settings?
    # Joint Status Publisher
    load_joint_state_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'joint_state_broadcaster'],
        output='screen'
    )

    # Path execution controller, which is the action?
    # How does the system know that the controller my_group_controller exists?
    load_joint_trajectory_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 
             'arm_controller'],
        output='screen'
    )

    # The following two estimates are used to control the startup order of each node.
    # Listen to spawn_entity_cmd, and start load_joint_state_controller when it exits (fully starts)?
    # close_evt1 =  RegisterEventHandler( 
    #         event_handler=OnProcessExit(
    #             target_action=spawn_entity_cmd,
    #             on_exit=[load_joint_state_controller],
    #         )
    # )
    # Monitor load_joint_state_controller, and start load_joint_trajectory_controller when it exits (fully starts)?
    # How does MoveIt connect with the actions provided by Gazebo?
    # close_evt2 = RegisterEventHandler(
    #         event_handler=OnProcessExit(
    #             target_action=load_joint_state_controller,
    #             on_exit=[load_joint_trajectory_controller],
    #         )
    # )

    delayed_controllers = TimerAction(
        period=5.0,
        actions=[
            load_joint_state_controller,
            load_joint_trajectory_controller
        ]
    )

    ld = LaunchDescription()

    # ld.add_action(close_evt1)
    # ld.add_action(close_evt2)

    ld.add_action(start_gazebo_cmd)
    ld.add_action(node_robot_state_publisher)
    ld.add_action(spawn_entity_cmd)
    ld.add_action(delayed_controllers)

    return ld

# export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=$IGN_GAZEBO_SYSTEM_PLUGIN_PATH:/opt/ros/humble/lib/
# colcon build --packages-select piper_description piper_gazebo
# ros2 launch piper_gazebo piper_no_gripper_gazebo.launch.py
# ros2 service list | grep controller_manager