# 
# by mijo

import hou


def scan_all_camera_nodes(node,cams):
    # �p�G�`�I�O��v������ (cam)�A�h��X��e�`�I�W��
    if str( node.type() ) == '<hou.NodeType for Object cam>':
        # print(node.path())
        cams.append(node)
    
    # ���j�M���Ҧ��l�`�I
    for child_node in node.children():
        scan_all_camera_nodes(child_node,cams)
        
def batch_set_camera_parameters(parameters):
    
    cams = []
    
    nodes = hou.selectedNodes()
    
    # ����Ҧ�����v��
    # cameras = hou.nodeTypeCategories()['cam']['perspective']
    scan_all_camera_nodes(nodes[0],cams)
    
    print( cams )
    
    # cam = nodes[0]
    
    # ���N�Ҧ���v���ó]�m�Ѽ�
    # for cam in cameras.instances():
    for cam in cams:
    # for cam in cam.instances():
        for param, value in parameters.items():
            try:
                cam.setParms({param: value})
                print(f"�]�m��v�� {cam.name()} �� {param} �ѼƬ� {value}")
            except hou.OperationFailed:
                print(f"�L�k�]�m��v�� {cam.name()} �� {param} �Ѽ�")
                

# �]�m�ѼƦr��A�o�̥i�H�ۦ�K�[�έק�ݭn�]�m���ѼƩM��
camera_parameters = {
    "resx": 2208,
    "resy": 1472,
    "aspect": 1 ,
    "near": 0.1,
    "far": 10000,
    "shutter": 0.48,
    # �b�o�̲K�[��h�ѼƩM��
}

batch_set_camera_parameters(camera_parameters)