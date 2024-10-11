import numpy as np

class ShaderMapper():
    def __init__(self, light_engine, N_part_max: int=1000):
        self.light_engine = light_engine
        self.N_part_max = N_part_max
        self.pixels_positions = np.zeros((self.N_part_max, 2), dtype=np.float32)
        self.pixels_color = np.zeros((self.N_part_max, 3), dtype=np.float32)
        self.pixels_group = list()
        self.current_pos = 0

    def add_light(self, light: object):
        if light.use_shader:
            self.addPixelsSubGroup(
                light,
            )
        print("ShaderMapper Lights:", self.pixels_group)

    def addPixelsSubGroup(
            self, 
            light: int, 
        ):
        self.pixels_group.append(
            PixelsSubGroup(
                light,
                input_vbo_pos=self.current_pos,
                output_vbo_pos=self.current_pos,
            )
        )
        self.current_pos += light.num_pixels

    def bind_position_in_vbo(self, vbo: object):
        for group in self.pixels_group:
            pos = group.input_vbo_pos
            N = group.pixels_number
            self.pixels_positions[pos:pos+N] = group.pixels_pos
        vbo.write(
            self.pixels_positions.tobytes()
        )

    def read_color(self, vbo: object):
        data = vbo.read()
        colors = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        for group in self.pixels_group:
            group.set_colors(colors)
    

class PixelsSubGroup():
    def __init__(self, 
            light: object,
            input_vbo_pos: int, 
            output_vbo_pos: int
        ):
        self.light = light
        self.pixels_number = light.num_pixels
        self.pixels_pos = light.canvas_position
        self.input_vbo_pos = input_vbo_pos
        self.output_vbo_pos = output_vbo_pos

    def __len__(self):
        return self.pixels_number

    def set_colors(self, color_buffer: np.ndarray):
        colors = color_buffer[self.output_vbo_pos:self.output_vbo_pos+len(self)]
        colors = colors[0, :3]
        self.light.update(colors)
