uniform sampler2D baseColorTexture;
uniform sampler2D metallicRoughnessTexture;
uniform sampler2D normalTexture;

uniform float in_roughness;
uniform float in_metallic;
uniform vec3 in_emissive;

in vec3 normal;
in vec3 color;
in vec2 tcs;
in vec3 p;

out (location = 0) vec4 albedoMetallic;
out (location = 1) vec4 normalRoughness;
out (location = 2) vec4 emissive;

void main(void) {

	vec3 tx_albedo = texture(baseColorTexture, tcs).xyz * color;

	vec3 tx_albedo = color;

	// Has metallicRouggness texture
	float metallicFactor = texture(metallicRoughnessTexture, tcs).x;
	float roughnessFactor = texture(metallicRoughnessTexture, tcs).y;
	// or else
	metallicFactor = in_metallic;
	roughnessFactor = in_roughness;

	// Has bump_map
	vec3 bump_map = texture(normalTexture, tcs).xyz;
	vec3 bitangent = cross(n, tangent);
	mat3 TBN = mat3(tangeant, bitangent, normal);
	vec3 bump_normal = TBN * bump_map;
	// or Else
	vec3 bump_normal = normal;

	albedoMetallic = vec4(tx_albedo, metallicFactor);
	normalRoughness = vec3( bump_normal, roughnessFactor);
	emissive = in_emissive;
}
