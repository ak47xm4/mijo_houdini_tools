# 
# by mijo

import hou


def scan_all_camera_nodes(node,cams):
    # 如果節點是攝影機類型 (cam)，則輸出當前節點名稱
    if str( node.type() ) == '<hou.NodeType for Object cam>':
        # print(node.path())
        cams.append(node)
    
    # 遞迴遍歷所有子節點
    for child_node in node.children():
        scan_all_camera_nodes(child_node,cams)
        
def batch_set_camera_parameters(parameters):
    
    cams = []
    
    nodes = hou.selectedNodes()
    
    # 獲取所有的攝影機
    # cameras = hou.nodeTypeCategories()['cam']['perspective']
    scan_all_camera_nodes(nodes[0],cams)
    
    print( cams )
    
    # cam = nodes[0]
    
    # 迭代所有攝影機並設置參數
    # for cam in cameras.instances():
    for cam in cams:
    # for cam in cam.instances():
        for param, value in parameters.items():
            try:
                cam.setParms({param: value})
                print(f"設置攝影機 {cam.name()} 的 {param} 參數為 {value}")
            except hou.OperationFailed:
                print(f"無法設置攝影機 {cam.name()} 的 {param} 參數")
                

# 設置參數字典，這裡可以自行添加或修改需要設置的參數和值
camera_parameters = {
    "resx": 2208,
    "resy": 1472,
    "aspect": 1 ,
    "near": 0.1,
    "far": 10000,
    "shutter": 0.48,
    # 在這裡添加更多參數和值
}

batch_set_camera_parameters(camera_parameters)