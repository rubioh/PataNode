# This shaders builder will build a principledBSDF shaders based on gltf2.0's blender specification

layout = "layout (location = "

position = ") in vec3 in_position;\n"
normal = ") in vec3 in_normal;\n"
tc = ") in vec2 in_tc;\n"
color = ") in vec3 in_color;\n"
tangent = ") in vec3 in_tangent;\n"

# matrix = "uniform mat4 model_transform; \n\
# 			uniform mat4 model;\n\
# 			uniform mat4 view;\n\
# 			uniform mat4 projection;\n"

matrix = "uniform mat4 model;\n\
		  uniform mat4 mvp;\n"

out = "out vec2 tcs;\n\
out vec3 normal;\n\
out vec3 p;\n\
out vec3 color;\n\
out vec3 tangent;\n"

out_tbn = "out mat3 tbn;\n"
in_tbn = "in mat3 tbn;\n"
#  mat4 mvp = model_transform * model *  view * projection;\n\
main = "void main() {\n\
    vec4 v = vec4(in_position, 1.);\n\
    v = v * mvp;\n\
    gl_Position = v;\n\
	p = v.xyz;\n"

col_inter = "color = in_color;\n"
normal_inter = "normal = (vec4(in_normal, 0.) * model).xyz;\n"

tbn_compute = " vec3 bitangent = cross(in_normal, in_tangent);\n\
   vec3 T = normalize(vec3(model * vec4(in_tangent,   0.0)));\n\
   vec3 B = normalize(vec3(model * vec4(bitangent, 0.0)));\n\
   vec3 N = normalize(vec3(model * vec4(in_normal,    0.0)));\n\
   tbn = mat3(T, B, N);\n"

tcs_inter = "tcs = in_tc;\n"
tangent_inter = "tangent = in_tangent;\n"

baseColorTexture = "uniform sampler2D baseColorTexture;\n"
metallicRoughnessTexture = "uniform sampler2D metallicRoughnessTexture;\n"
normalTexture = "uniform sampler2D normalTexture;\n"

uniform_albedo = "uniform vec4 in_albedo;\n"
uniform_roughness = "uniform float in_roughness;\n"
uniform_metallic = "uniform float in_metallic;\n"
uniform_emissive = "uniform vec4 in_emissive;\n"

uniform_fragment_in = "in vec3 normal;\n\
in vec3 color;\n\
in vec2 tcs;\n\
in vec3 p;\n\
in vec3 tangent;\n"

fragment_out = "layout(location = 0) out vec4 albedoMetallic;\n\
layout(location = 1) out vec4 normalRoughness;\n\
layout(location = 2) out vec4 emissive;\n"

fragment_main = "void main(void) {\n\
\n"

color_texture = (
    "vec3 tx_albedo = texture(baseColorTexture, tcs).xyz * color * in_albedo.xyz;\n"
)
color_no_texture = "vec3 tx_albedo = color * in_albedo.xyz;\n"

# todo metallic
metallic_rougness_texture = "float metallicFactor = in_metallic * 0.000001 * texture(metallicRoughnessTexture, tcs).x;\n\
	float roughnessFactor = in_roughness * texture(metallicRoughnessTexture, tcs).y;\n"

metallic_roughness_no_texture = "	float metallicFactor = in_metallic;\n\
	float roughnessFactor = in_roughness;\n"

normal_texture = "	vec3 bump_map = texture(normalTexture, tcs).xyz;\n\
bump_map = bump_map * 2.0 - 1.0;\n\
vec3 bump_normal = normalize(tbn * bump_map);\n"

normal_no_texture = "vec3 bump_normal = normal;\n"

fragment_end = "	albedoMetallic = vec4(tx_albedo, metallicFactor);\n\
	normalRoughness = vec4( bump_normal, roughnessFactor);\n\
	emissive.xyz = in_emissive.xyz;\n"


def build_vertex_shader(mesh_layout):
    shader = ""
    shader += layout + str(0) + position
    layout_index = 1
    if mesh_layout["vertex_normal"]:
        shader += layout + str(layout_index) + normal
        layout_index = layout_index + 1
    if mesh_layout["vertex_tcs"]:
        shader += layout + str(layout_index) + tc
        layout_index = layout_index + 1
    if mesh_layout["vertex_color"]:
        shader += layout + str(layout_index) + color
        layout_index = layout_index + 1
    if mesh_layout["vertex_tangent"]:
        shader += layout + str(layout_index) + tangent
        layout_index = layout_index + 1

    shader += matrix
    shader += out
    if mesh_layout["vertex_tangent"]:
        shader += out_tbn

    shader += main
    if mesh_layout["vertex_normal"]:
        shader += normal_inter
    else:
        shader += "normal = vec3(1., 0., 0.);\n"

    if mesh_layout["vertex_tangent"]:
        shader += tbn_compute
    if mesh_layout["vertex_tcs"]:
        shader += tcs_inter
    else:
        shader += "tcs = vec2(1.);\n"

    if mesh_layout["vertex_color"]:
        shader += col_inter
    else:
        shader += "color = vec3(1.);\n"

    if mesh_layout["vertex_tangent"]:
        shader += tangent_inter
    else:
        shader += "tangent = vec3(1., 0., 0.);\n"
    shader += "}"
    return shader


def build_fragment_shader(material):
    result = ""
    if "baseColorTexture" in material.textures:
        result += baseColorTexture
    if "metallicRoughnessTexture" in material.textures:
        result += metallicRoughnessTexture
    if "normalTexture" in material.textures:
        result += normalTexture

    # 	if not "metallicRoughnessTexture" in material.textures:
    # 		result += uniform_roughness + uniform_metallic

    result += uniform_albedo
    result += uniform_roughness
    result += uniform_metallic
    result += uniform_emissive
    result += uniform_fragment_in

    if "normalTexture" in material.textures:
        result += in_tbn

    result += fragment_out
    result += fragment_main

    if "baseColorTexture" in material.textures:
        result += color_texture
    else:
        result += color_no_texture

    if "metallicRoughnessTexture" in material.textures:
        result += metallic_rougness_texture
    else:
        result += metallic_roughness_no_texture

    if "normalTexture" in material.textures:
        result += normal_texture
    else:
        result += normal_no_texture

    result += fragment_end

    result += "albedoMetallic.x += tcs.x * 0.000001;\n"
    result += "}"
    return result


def build_shaders(mesh_layout, material):
    return (build_vertex_shader(mesh_layout), build_fragment_shader(material))
