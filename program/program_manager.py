import numpy as np
import moderngl as mgl
from copy import deepcopy

from program.program_conf import SHADER_PROGRAMS, LoadingFBOsError


DEBUG = False

class ProgramManager:

    def __init__(self):
        pass


class FBOManager:

    def __init__(self, ctx):
        self.ctx = ctx
        # Register lists of FBOs according to the hash of win_size, components and dtype
        self.current_fbos = {}
        # TODO in_use fbos logic for complex program 
        self.in_use_fbos = {}

        # base params
        self._default_dtype = 'f4'
        self._default_component = 4


    def restoreFBOUsability(self):
        if DEBUG: print(self.in_use_fbos)
        for hashmap, fbos in self.in_use_fbos.items():
            for i in range(len(fbos)):
                self.in_use_fbos[hashmap][i] = 0
        if DEBUG: print(self.in_use_fbos)


    def getFBO(self, win_sizes=[], components=None, dtypes=None, depth_requirements=None, num_textures = None):
        if dtypes is not None and len(dtypes) != len(win_sizes):
            print('FBOManager::getFBO lists win_sizes and dtypes are not of the same size')
            return None
        if components is not None and len(components) != len(win_sizes):
            print('FBOManager::getFBO lists win_sizes and components are not of the same size')
            return None
        if DEBUG: print("getFBOs:: in current FBOs :", self.current_fbos)
        if DEBUG: print("getFBOs:: in current in_use:", self.in_use_fbos)
        hashmaps = self.getHashmaps(win_sizes, components, dtypes, depth_requirements, num_textures)
        #returned_fbos = [None for i in range(len(hashmaps))]
        returned_fbos = self.checkForExistingFBOs(hashmaps)
        for i in range(len(win_sizes)):
            current_hashmap = hashmaps[i]
            if returned_fbos[i] is not None:
                continue
            if dtypes is not None:
                dtype = dtypes[i]
            else:
                dtype = self._default_dtype
            win_size = win_sizes[i]
            if components is not None:
                component = components[i]
            else:
                component = self._default_component

            if num_textures:
                new_textures =  [self.ctx.texture(size=win_size, components=component, dtype=dtype) 
                    for j in range(num_textures[i])]
            else:
                new_textures =  self.ctx.texture(size=win_size, components=component, dtype=dtype)
            if depth_requirements is not None:
                depth = depth_requirements[i]
            else:
                depth = False
            if depth:
                depth_texture = self.ctx.depth_renderbuffer(size=win_size)
                new_fbo = self.ctx.framebuffer(color_attachments=new_textures, depth_attachment=depth_texture)
            else:
                new_fbo = self.ctx.framebuffer(color_attachments=new_textures)
            returned_fbos[i] = new_fbo
            if not current_hashmap in self.current_fbos.keys():
                self.current_fbos[current_hashmap] = []
                self.in_use_fbos[current_hashmap] = []

            self.current_fbos[current_hashmap].append(new_fbo)
            self.in_use_fbos[current_hashmap].append(1)
        if DEBUG: print("getFBOs:: out current FBOs:", self.current_fbos)
        if DEBUG: print("getFBOs:: out current in_use:", self.in_use_fbos)
        return returned_fbos


    def checkForExistingFBOs(self, hashmaps):
        returned_fbos = [None for i in range(len(hashmaps))]
        if DEBUG: print("checkForExistingFBOs:: Current hashmap : ", hashmaps, "\nCurrent fbos", self.current_fbos.keys())
        for i, hashmap in enumerate(hashmaps):
            if hashmap in self.current_fbos.keys():
                for j, fbo in enumerate(self.current_fbos[hashmap]):
                    # In use logic
                    if not self.in_use_fbos[hashmap][j]:
                        returned_fbos[i] = self.current_fbos[hashmap][j]
                        self.in_use_fbos[hashmap][j] = 1
                        break

        if DEBUG: print("checkForExistingFBOs:: Returned fbos after checking:", returned_fbos)
        return returned_fbos


    def getHashmaps(self, win_sizes, components=None, dtypes=None, depths=None, num_textures=None):
        hashmaps = list()
        for i, win_size in enumerate(win_sizes):
            if components is not None:
                component = components[i]
            else:
                component = self._default_component
            if dtypes is not None:
                dtype = dtypes[i]
            else:
                dtype = self._default_dtype
            if depths is not None:
                depth = 1
            else:
                depth = 0
            if num_textures is not None:
                num_texture = num_textures[i]
            else:
                num_texture = 1
            hashmap = self.propertiesToHashmap(win_size, component, dtype, depth, num_texture)
            hashmaps.append(hashmap)
        return hashmaps


    def propertiesToHashmap(self, win_size, component, dtype, depth, num_texture):
        hashmap = str(win_size[0]+win_size[1]*10000)
        hashmap += str(component)
        dtype_to_int = [ord(c) for c in dtype]
        hashmap += str(sum(dtype_to_int))
        hashmap += str(depth)
        hashmap += str(num_texture)
        hashmap = int(hashmap)
        return hashmap

