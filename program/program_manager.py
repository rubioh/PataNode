import numpy as np
import moderngl as mgl

from program.program_conf import SHADER_PROGRAMS


class ProgramManager:

    def __init__(self):
        pass


class FBOManager:

    def __init__(self, ctx):
        self.ctx = ctx
        # Register all current fbo ordered by size
        self.current_fbos = {}


    def getFBO(self, win_sizes=[], components=None, dtypes=None):
        if dtypes is not None and len(dtypes) != len(win_sizes):
            print('FBOManager::getFBO lists win_sizes and dtypes are not of the same size')
            return None
        if components is not None and len(components) != len(win_sizes):
            print('FBOManager::getFBO lists win_sizes and components are not of the same size')
            return None

        returned_fbos = list()
        for i in range(len(win_sizes)):
            if dtypes is not None:
                dtype = dtypes[i]
            else:
                dtype = 'f4'
            win_size = win_sizes[i]
            if components is not None:
                component = components[i]
            else:
                component = 4
            new_texture = self.ctx.texture(size=win_size, components=component, dtype=dtype)
            new_fbo = self.ctx.framebuffer(color_attachments=new_texture)

            returned_fbos.append(new_fbo)
            if not win_size in self.current_fbos.keys():
                self.current_fbos[str(win_size)] = []

            self.current_fbos[str(win_size)].append(new_fbo)

        return returned_fbos



