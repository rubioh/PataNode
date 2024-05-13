uniform sampler2D albedoMetallicTexture;
uniform sampler2D normalRoughnessTexture;
uniform sampler2D emissiveTexture;
//uniform sampler2D shadowmap;

uniform mat4 camera;
uniform vec3 lightDir;
uniform vec3 lightColor;
uniform vec3 ambient;

out vec4 colorEmission;

in vec2 p;

float VisibilityTerm(float roughness, float ndotv, float ndotl)
{
	float r2 = roughness * roughness;
	float gv = ndotl * sqrt(ndotv * (ndotv - ndotv * r2) + r2);
	float gl = ndotv * sqrt(ndotl * (ndotl - ndotl * r2) + r2);
	return 0.5 / max(gv + gl, 0.00001);
}

float DistributionTerm(float roughness, float ndoth)
{
	float r2 = roughness * roughness;
	float d = (ndoth * r2 - ndoth) * ndoth + 1.0;
	return r2 / (d * d * MATH_PI);
}

vec3 FresnelTerm(vec3 specularColor, float vdoth)
{
	vec3 fresnel = specularColor + (1. - specularColor) * pow((1. - vdoth), 5.);
	return fresnel;
}

void main() {

	vec3 viewDir = camera[3].xyz;

	vec4 albedoMetallic = texture( albedoMetallicTexture, p);
	vec4 normalRoughness = texture( normalRoughnessTexture, p);
	vec3 emissive = texture(emissiveTexture, p).xyz;

	vec3 normal = normalRoughness.xyz;
	vec3 diffuseColor = mix(albedoMetallic.xyz, vec3(0.), albedoMetallic.w);
	vec3 specularColor = mix(vec3(.02), albedoMetallic.xyz, albedoMetallic.w);

	vec3 refl = reflect(-viewDir, normal);

	float roughnessE = normalRoughness.w * normalRoughness.w;
	float roughnessL = max(.01, roughnessE);
	float ndotl = max(0.05, dot(normal, lightDir));
	colorEmission.xyz = specularColor * lightColor * ndotl
	+ emissive;
	vec3 specular = vec3(0.);
	float ndotv = max(0., dot(normal, viewDir) );
	float specularFactor = pow(ndotv, roughnessE );
}