import numpy as np


class PixelsView():
    def __init__(self, N_part_max: int=2000):
        self.N_part_max = N_part_max
        self.pixels_positions = np.zeros((self.N_part_max, 2), dtype=np.float32)
        self.pixels_color = np.zeros((self.N_part_max, 3), dtype=np.float32)
        self.pixels_group = {}
        self.current_pos = 0

    def addPixelsSubGroup(
            self, 
            pixels_number: int, 
            pixels_pos: int,
            name: str="toto"
        ):
        self.pixels_group[name] = PixelsSubGroup(
            pixels_number, 
            pixels_pos,
            input_vbo_pos=self.current_pos,
            output_vbo_pos=self.current_pos,
        )
        
        self.current_pos += pixels_number

    def removePixelsSubGroup(
        self,
        name: str="toto"
    ):
        pass

    def bind_position_in_vbo(self, vbo: object):
        for name, group in self.pixels_group.items():
            pos = group.input_vbo_pos
            N = group.pixels_number
            self.pixels_positions[pos:pos+N] = group.pixels_pos
        vbo.write(
            self.pixels_positions.tobytes()
        )

    def read_color(self, vbo: object):
        data = vbo.read()
        colors = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        for name, group in self.pixels_group.items():
            group.set_colors(colors)
    

class PixelsSubGroup():
    def __init__(self, 
            pixels_number: int, 
            pixels_pos: list, 
            input_vbo_pos: int, 
            output_vbo_pos: int
        ):
        self.pixels_number = pixels_number
        self.pixels_pos = pixels_pos
        self.input_vbo_pos = input_vbo_pos
        self.output_vbo_pos = output_vbo_pos

    def __len__(self):
        return self.pixels_number

    def set_colors(self, color_buffer: np.ndarray):
        self.colors = color_buffer[self.output_vbo_pos:self.output_vbo_pos+len(self)]
