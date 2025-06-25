DEBUG = False


class ProgramManager:
    def __init__(self):
        pass


class FBOManager:
    def __init__(self, ctx):
        self.ctx = ctx

        # Register lists of FBOs according to the hash of win_size, components and dtype
        self.current_fbos = {}

        # TODO in_use fbos logic for complex program
        self.in_use_fbos = {}

        # Base params
        self._default_dtype = "f4"
        self._default_component = 4

    def restoreFBOUsability(self):
        if DEBUG:
            print(self.in_use_fbos)

        for hashmap, fbos in self.in_use_fbos.items():
            for i in range(len(fbos)):
                self.in_use_fbos[hashmap][i] = 0

        if DEBUG:
            print(self.in_use_fbos)

    def getFBO(
        self,
        win_sizes=[],
        components=None,
        dtypes=None,
        depth_requirements=None,
        num_textures=None,
    ):
        if dtypes is not None and len(dtypes) != len(win_sizes):
            print(
                "FBOManager::getFBO lists win_sizes and dtypes are not of the same size"
            )
            return None

        if components is not None and len(components) != len(win_sizes):
            print(
                "FBOManager::getFBO lists win_sizes and components are not of the same size"
            )
            return None

        if DEBUG:
            print("getFBOs:: in current FBOs :", self.current_fbos)
            print("getFBOs:: in current in_use:", self.in_use_fbos)

        hashes = self.getHashes(
            win_sizes, components, dtypes, depth_requirements, num_textures
        )
        #       returned_fbos = [None for i in range(len(hashes))]
        returned_fbos = self.checkForExistingFBOs(hashes)

        for i in range(len(win_sizes)):
            current_hash = hashes[i]

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

            new_textures = [
                self.ctx.texture(size=win_size, components=component, dtype=dtype)
                for j in range(num_textures[i])
            ]

            if depth_requirements is not None:
                depth = depth_requirements[i]
            else:
                depth = False

            if depth:
                depth_texture = self.ctx.depth_renderbuffer(size=win_size)
                new_fbo = self.ctx.framebuffer(
                    color_attachments=new_textures, depth_attachment=depth_texture
                )
            else:
                new_fbo = self.ctx.framebuffer(color_attachments=new_textures)

            returned_fbos[i] = new_fbo

            if current_hash not in self.current_fbos.keys():
                self.current_fbos[current_hash] = []
                self.in_use_fbos[current_hash] = []

            self.current_fbos[current_hash].append(new_fbo)
            self.in_use_fbos[current_hash].append(1)

        if DEBUG:
            print("getFBOs:: out current FBOs:", self.current_fbos)
            print("getFBOs:: out current in_use:", self.in_use_fbos)

        return returned_fbos

    def checkForExistingFBOs(self, hashes):
        returned_fbos = [None for i in range(len(hashes))]

        if DEBUG:
            print(
                "checkForExistingFBOs:: Current hashmap:",
                hashes,
                "\nCurrent fbos",
                self.current_fbos.keys(),
            )

        for i, current_hash in enumerate(hashes):
            if current_hash in self.current_fbos.keys():
                for j, fbo in enumerate(self.current_fbos[current_hash]):
                    # In use logic
                    if not self.in_use_fbos[current_hash][j]:
                        returned_fbos[i] = self.current_fbos[current_hash][j]
                        self.in_use_fbos[current_hash][j] = 1
                        break

        if DEBUG:
            print("checkForExistingFBOs:: Returned fbos after checking:", returned_fbos)

        return returned_fbos

    def getHashes(
        self, win_sizes, components=None, dtypes=None, depths=None, num_textures=None
    ):
        hashes = list()

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

            current_hash = self.propertiesToHash(
                win_size, component, dtype, depth, num_texture
            )
            hashes.append(current_hash)

        return hashes

    def propertiesToHash(self, win_size, component, dtype, depth, num_texture):
        current_hash = str(win_size[0] + win_size[1] * 10000)
        current_hash += str(component)
        dtype_to_int = [ord(c) for c in dtype]
        current_hash += str(sum(dtype_to_int))
        current_hash += str(depth)
        current_hash += str(num_texture)
        current_hash = int(current_hash)
        return current_hash
