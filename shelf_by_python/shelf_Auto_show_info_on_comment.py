# fusion style houdini local cache
# by mijo

'''
roadmap:
    click and show the node info I want

features 20221120 :
    ROP:
        fetch

future features :
    show nodes info
'''

import hou


nodes = hou.selectedNodes()

for n in nodes :
    node_type = str(n.type())
    if node_type == '<hou.NodeType for Driver fetch>' :
        
        fetch_source_Str = n.parm('source').unexpandedString()
        
        fetch_Comment = 'fetch Path : \n'
        fetch_Comment += fetch_source_Str
        
        n.setComment(fetch_Comment)
        n.setGenericFlag(hou.nodeFlag.DisplayComment, True)