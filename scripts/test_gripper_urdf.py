import xml.etree.ElementTree as ET
import sys

path = sys.argv[1]
tree = ET.parse(path)
root = tree.getroot()

# Remove old Gazebo Classic mimic plugin
for gazebo in root.findall("gazebo"):
    for plugin in gazebo.findall("plugin"):
        filename = plugin.get("filename", "")
        if "mimic_joint_plugin" in filename:
            gazebo.remove(plugin)

# Temporarily remove URDF mimic relationship
joint2 = root.find("./joint[@name='finger_joint2']")
if joint2 is not None:
    mimic = joint2.find("mimic")
    if mimic is not None:
        joint2.remove(mimic)

tree.write(path, encoding="unicode")
print("Diagnostic gripper patch applied")