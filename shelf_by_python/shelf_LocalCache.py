# fusion style houdini local cache
# by mijo

'''
roadmap:
    efficent to use , preview

features 20221119 :
    copy filecache files to local
    and create file node to read cache
    
    in blackmagic fusion style OTZ

future features :
    local to network  and  network to local
    easy to define where is copy to
        now is using LocalCache_path to define 
        
    smart to know where is copy from
    
    more speed more performance
    
    create comment to record
        copy time
    
    compare difference
    
    use take to control
        switch orinal and local
        efficent to use , preview
        netwrok render farm friendly
        
'''

'''
video (tutorial?) :
https://www.youtube.com/watch?v=ukIjS8A3gsQ
'''

import os

import shutil
# import pyfastcopy # faster!!!!

import hou
import win32file # need install module
from pathlib import Path

LocalCache_path = 'H:/h_cache/'


nodes = hou.selectedNodes()
##############################################################################################################
# functions

def is_netfile( path ):
    path = path.replace('\\','/')
    ddd = path.split('/')
    ddd = ddd[0]
    ddd += '\\'
    return win32file.GetDriveType(ddd) == win32file.DRIVE_REMOTE
    # return win32file.GetDriveType(path) == win32file.DRIVE_FIXED
    








# functions
##############################################################################################################

print("-----------------------------------")

for n in nodes :
    #print(n.name())
    node_type = str(n.type())
    #print(node_type)
    
    # temporary
    if node_type == '<hou.SopNodeType for Sop filecache::2.0>' :
        geo_node = n.parent() # sop geo
        name = str(n.name())
        
        file_node_Name = ("file_" + name )
        
        file_node_Exist = False # test... will delete in future
        
        #print(geo_node.path()+'/'+file_node_Name)
        
        file_node = hou.node(geo_node.path()+'/'+file_node_Name)
        #print(file_node)
        if file_node == None:
            # the node does not exist
            file_node = geo_node.createNode("file", node_name = file_node_Name )
            file_node_Exist = False
        else:
            # the node does exist
            file_node_Exist = True
        
        filename = n.parm("file").eval() # eval file cache path
        
        # test network driver
        # print('is_netfile : ')
        print(file_node_Name+' == netfile : ' + str( is_netfile(filename) ))
        
        # node position
        node_pos = n.position()
        #print(node_pos)
        file_node.setPosition([node_pos[0]+4, node_pos[1]])
        
        cache_files_dir = Path(filename).parent.absolute() # get dir folder path
        cache_files_dir = str(cache_files_dir) # for safe
        cache_files_dir = cache_files_dir.replace('\\','/') # fuck \
        cache_files_name = os.path.basename(filename) # get file name
        cfn_split = cache_files_name.split('.') #cache_files_name_split_list    shortly
        
        # fusion style local cache
        local_cache_filename_dir = cache_files_dir.replace('/','!')
        local_cache_filename_dir = local_cache_filename_dir.replace(':','')
        # print(local_cache_filename_dir)
        local_cache_file_dir = LocalCache_path+local_cache_filename_dir+'/'
        
        # temporary method
        local_cache_filename = local_cache_file_dir+cfn_split[0]+'.'+'$F'+'.'+cfn_split[-2]+'.'+cfn_split[-1]
        #print(local_cache_filename)
        
        # set file node file parm
        file_node.parm("file").set(local_cache_filename)
        
        # path to copy files
        src = cache_files_dir
        dest = local_cache_file_dir
        
        # create folder
        if not os.path.exists(local_cache_file_dir):
            os.makedirs(local_cache_file_dir)
            
        # copy files 0010
        
        # check empty ?
        path_defined = True
        try:
            src_files = os.listdir(src)
        except:
            empty_message = '!!!! nothing in "'+name+'"'
            hou.ui.displayMessage(empty_message)
            print(empty_message)
            path_defined = False
        
        # copy files 0020
        if path_defined :
            with hou.InterruptableOperation("copying cache WIP",open_interrupt_dialog = True) as operation:
                src_files_len = len(src_files)
                i=0
                for file_name in src_files:
                    full_file_name = os.path.join(src, file_name)
                    if (os.path.isfile(full_file_name)):
                        # shutil.copy(full_file_name, dest)
                        shutil.copyfile(full_file_name, dest+'/'+file_name)
                        
                    i +=1 
                    precent = float(i)/float(src_files_len)
                    operation.updateProgress(precent)
            
            print(str(n.name())+"____copy cache complete")
        
print("-----------------------------------")
print("all complete")