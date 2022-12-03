# fusion style houdini local cache
# by mijo

'''

roadmap:
    efficent to use , preview
    
future features :
    easy to define where is copy to
        now is using LocalCache_path to define 
        
    smart to know where is copy from
    
    create comment to record
        copy time?
    
    compare difference
    to not copy sam file
    
    use take to control
        switch orinal and local
        efficent to use , preview
        netwrok render farm friendly
    
    work with pdg 
    
done future features :
    #OK+WIP# local to network  and  network to local
    #OK+WIP# more speed more performance
    #OK+WIP# copy in BG

features 20221119 :
    copy filecache files to local
    and create file node to read cache
    
    in blackmagic fusion style OTZ

features 20221127 :
    function is_netfile
    more speed more performance
    copy in BG
    
features 20221203 :
    manual define local driver
    copy in BG
    
    
not slove yet:
    only supprot $F.bgeo.sc NOW
    
    manual define local driver
    or
    use win32 module

test env:
    houdini 19.5.368
    qlib
    labs

video (tutorial?) :
https://www.youtube.com/watch?v=ukIjS8A3gsQ

'''

##############################################################################################################
# start
import os

import shutil
# import pyfastcopy # faster!!!!

import hou
# import win32file # need install module
import subprocess
from pathlib import Path

LocalCache_path = 'H:/h_cache/'
networkDriverCache_path = '$HIP/geo/'
networkDriverCache_path_expandString = hou.text.expandString(networkDriverCache_path)

# manual define local driver
localDrivers = ['C:','D:','E:','F:','H:','I:']

# start
##############################################################################################################
# functions
'''
def is_netfile( path ):
    path = path.replace('\\','/')
    ddd = path.split('/')
    ddd = ddd[0]
    ddd += '\\'
    return win32file.GetDriveType(ddd) == win32file.DRIVE_REMOTE
    # return win32file.GetDriveType(path) == win32file.DRIVE_FIXED
'''

def is_netfile( path ):
    path = path.replace('\\','/')
    ddd = path.split('/')
    ddd = ddd[0]
    return ddd not in localDrivers
    # return win32file.GetDriveType(path) == win32file.DRIVE_FIXED


# functions
##############################################################################################################
# process

print("-----------------------------------")

nodes = hou.selectedNodes()

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
        cache_is_on_netDriver = is_netfile(filename)
        print(file_node_Name+' == netfile : ' + str( cache_is_on_netDriver ))
        
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
        
        goal_cache_file_dir = ''
        
        if cache_is_on_netDriver :
            goal_cache_file_dir = LocalCache_path+local_cache_filename_dir+'/'
        else:
            goal_cache_file_dir = networkDriverCache_path +local_cache_filename_dir+'/'
        
        # temporary method
        # for xxxx.bgeo.sc
        local_cache_filename = goal_cache_file_dir+cfn_split[0]+'.'+'$F'+'.'+cfn_split[-2]+'.'+cfn_split[-1]
        #print(local_cache_filename)
        
        # set file node file parm
        file_node.parm("file").set(local_cache_filename)
        
        # path to copy files
        src = cache_files_dir
        if cache_is_on_netDriver :
            dest = goal_cache_file_dir
        else:
            dest = hou.text.expandString(goal_cache_file_dir)
        
        # create folder
        if not os.path.exists(dest):
            if cache_is_on_netDriver :
                os.makedirs(dest)
            else:
                print('dest')
                print(dest)
                try:
                    os.makedirs(dest)
                except:
                    print('net_path_exist~~~~')
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
            
            '''
            # legacy less speed and hard to use. low speed
            
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
                    
            # src_files_len = len(src_files)
            
            # legacy less speed and hard to use. low speed
            '''
            
            
            # new copy method for win 
            copy_cmd_list = ['']
            cmd_safe_arg_len_index = 0
            
            for file_name in src_files:
                full_file_name = os.path.join(src, file_name)
                cmd_copy_src = full_file_name
                cmd_copy_src = cmd_copy_src.replace('/','\\')
                cmd_copy_dst = dest+'/'+file_name
                cmd_copy_dst = cmd_copy_dst.replace('/','\\')
                cmd2 = 'copy "'+cmd_copy_src+'" "'+cmd_copy_dst+'" & '
                
                # print(cmd_copy_dst)
                
                # there is a limit at cmd arg string length
                if len(copy_cmd_list[cmd_safe_arg_len_index]) > (8000-len(cmd2)) :
                    cmd_safe_arg_len_index += 1
                    copy_cmd_list.append( '' )
                copy_cmd_list[cmd_safe_arg_len_index] += cmd2
                    
                
            for i in copy_cmd_list:
                result=subprocess.Popen(i , stdout=subprocess.PIPE, stderr=subprocess.STDOUT , shell=True)
            # new copy method for win 
            
            print('copy cmd num: '+str(len(copy_cmd_list)))
            print(str(n.name())+"____copy cache complete")
        
print("-----------------------------------")
print("all complete , wait for lag~~~~~~~")



# process









