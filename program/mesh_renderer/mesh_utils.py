import struct

import glm
import numpy as np


def buffer_as_np_array(buffer, element_size, element_count, type):
    return np.array(buffer, type)


class MeshBufferAccessor:
    def __init__(self, buffer, element_size, t, element_count):
        self.buffer = buffer
        self.element_size = element_size
        self.t = t
        self.element_count = element_count
        self.char = "I"

        if self.element_size == 2 and self.t is not float:
            self.char = "H"

        if self.t is float:
            self.char = "f"

        self.char *= self.element_count

    def __getitem__(self, index):
        index = index * self.element_size * self.element_count
        ret = struct.unpack(
            self.char,
            self.buffer[index : index + self.element_size * self.element_count],
        )
        return ret

    def __setitem__(self, index, value):
        index = index * self.element_size * self.element_count
        self.buffer[index : index + self.element_size * self.element_count] = (
            struct.pack(self.char.value)
        )

    def size(self):
        return int(len(self.buffer) / (self.element_size * self.element_count))


def get_vertice(indice_accessor, vertices_accessor, index):
    vertice_index = indice_accessor[index][0]
    return vertices_accessor[vertice_index]


# WIP
def compute_tangent(in_indices, in_tcs, in_normals, in_position, indice_size):
    position = MeshBufferAccessor(in_position, 4, float, 3)
    tcs = MeshBufferAccessor(in_tcs, 4, float, 2)
    normal = MeshBufferAccessor(in_normals, 4, float, 3)
    indices = MeshBufferAccessor(in_indices, indice_size, int, 1)
    tangent_buffer = bytes(len(in_normals))
    tangents = MeshBufferAccessor(tangent_buffer, 4, float, 3)

    for i in range(int(indices.size() / 3)):
        p00 = glm.vec3(get_vertice(indices, position, i))
        t00 = glm.vec2(get_vertice(indices, tcs, i))
        n00 = glm.vec3(get_vertice(indices, normal, i))
        p01 = glm.vec3(get_vertice(indices, position, i + 1))
        t01 = glm.vec2(get_vertice(indices, tcs, i + 1))
        n01 = glm.vec3(get_vertice(indices, normal, i + 1))
        p11 = glm.vec3(get_vertice(indices, position, i + 2))
        t11 = glm.vec2(get_vertice(indices, tcs, i + 2))
        n11 = glm.vec3(get_vertice(indices, normal, i + 2))

        edge1 = p01 - p00
        edge2 = p02 - p01
        deltaUV1 = t01 - t00
        deltaUV2 = t02 - t01

        inverse_discriminant = 1.0 / (deltaUV1.x * deltaUV2.y - deltaUV2.x * deltaUV1.y)
        tangent - glm.vec3(0.0, 0.0, 0.0)
        tangent[0] = inverse_discriminant * (
            deltaUV2.y * edge1.x - deltaUV1.y * edge2.x
        )
        tangent[1] = inverse_discriminant * (
            deltaUV2.y * edge1.y - deltaUV1.y * edge2.y
        )
        tangent[2] = inverse_discriminant * (
            deltaUV2.y * edge1.z - deltaUV1.y * edge2.z
        )
        tangents[i] = tangent
        tangents[i + 1] = tangent
        tangents[i + 2] = tangent
    return tangent.buffer
    return 0
