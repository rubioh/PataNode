# This shaders builder will build a principledBSDF shaders based on gltf2.0's blender specification

layout = "layout (location = "

position = ") in vec3 in_position;\n"
normal = ") in vec3 in_normal;\n"
tc = ") in vec2 in_tc;\n"
color = ") in vec3 in_color;\n"

matrix = "uniform mat4 model_transform; \n\
			uniform mat4 model;\n\
			uniform mat4 view;\n\
			uniform mat4 projection;\n"

out = "out vec2 tcs;\n\
out vec3 normal;\n\
out vec3 p;\n\
out vec3 color;\n"

main = "void main() {\n\
    vec4 v = vec4(in_position, 1.);\n\
    mat4 mvp = model_transform * model *  view * projection;\n\
    v = v * mvp;\n\
    gl_Position = v;\n\
	p = v.xyz;\n"

col_inter = "col = in_color;\n"
normal_inter = "normal = (vec4(in_normal, 0.) * mvp).xyz;\n"
tcs_inter = "tcs = in_tc;\n"

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
"
fragment_out = "layout(location = 0) out vec4 albedoMetallic;\n\
layout(location = 1) out vec4 normalRoughness;\n\
layout(location = 2) out vec4 emissive;\n"

fragment_main = "void main(void) {\n\
\n"

color_texture =	"vec3 tx_albedo = texture(baseColorTexture, tcs).xyz * color * in_albedo.xyz;\n"
color_no_texture = "vec3 tx_albedo = color * in_albedo.xyz;\n"

metallic_rougness_texture = "float metallicFactor = in_metallic * texture(metallicRoughnessTexture, tcs).x;\n\
	float roughnessFactor = in_roughness * texture(metallicRoughnessTexture, tcs).y;\n"

metallic_roughness_no_texture = "	float metallicFactor = in_metallic;\n\
	float roughnessFactor = in_roughness;\n"

normal_texture = "	vec3 bump_map = texture(normalTexture, tcs).xyz;\n\
	vec3 bitangent = cross(n, tangent);\n\
	mat3 TBN = mat3(tangeant, bitangent, normal);\n\
	vec3 bump_normal = TBN * bump_map;\n"

normal_no_texture = "vec3 bump_normal = normal;\n"

fragment_end = "	albedoMetallic = vec4(tx_albedo, metallicFactor);\n\
	normalRoughness = vec4( bump_normal, roughnessFactor);\n\
	emissive.xyz = in_emissive.xyz;\n\
}\n"

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
	shader += matrix
	shader += out
	shader += main
	if mesh_layout["vertex_normal"]:
		shader += normal_inter
	else:
		shader += "normal = vec3(1., 0., 0.);\n"

	if mesh_layout["vertex_tcs"]:
		shader += tcs_inter
	else:
		shader += "tcs = vec2(1.);\n"

	if mesh_layout["vertex_color"]:
		shader += col_inter
	else:
		shader += "color = vec3(1.);\n"
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
	
#	if not "metallicRoughnessTexture" in material.textures:
#		result += uniform_roughness + uniform_metallic

	result += uniform_albedo
	result += uniform_roughness
	result += uniform_metallic
	result += uniform_emissive
	result += uniform_fragment_in
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
	return result

def build_shaders(mesh_layout, material):
	return (build_vertex_shader(mesh_layout), build_fragment_shader(material))