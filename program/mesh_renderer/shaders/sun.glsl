uniform sampler2D albedoMetallicTexture;
uniform sampler2D normalRoughnessTexture;
uniform sampler2D emissiveTexture;
//uniform sampler2D shadowmap;

uniform mat4 view;
uniform vec3 lightDir;
uniform vec3 lightColor;

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
	return r2 / (d * d * 3.141592);
}

vec3 FresnelTerm(vec3 specularColor, float vdoth)
{
	vec3 fresnel = specularColor + (1. - specularColor) * pow((1. - vdoth), 5.);
	return fresnel;
}

void main() {

	vec3 viewDir = view[3].xyz;
	vec2 tc = (p + 1.) * .5;
	vec4 albedoMetallic = texture( albedoMetallicTexture, tc);
	vec4 normalRoughness = texture( normalRoughnessTexture, tc);
	vec3 emissive = texture(emissiveTexture, tc).xyz;

	vec3 normal = normalRoughness.xyz;
	vec3 diffuseColor = mix(albedoMetallic.xyz, vec3(0.), albedoMetallic.w);
	vec3 specularColor = mix(vec3(.02), albedoMetallic.xyz, albedoMetallic.w);

	vec3 refl = reflect(-viewDir, normal);

	float roughnessE = normalRoughness.w * normalRoughness.w;
	float roughnessL = max(.01, roughnessE);
	float ndotl = max(0.05, dot(normal, lightDir));
	colorEmission.xyz = diffuseColor * lightColor * ndotl
	+ emissive + refl/1999. + specularColor * 0.001;
	vec3 specular = vec3(0.);
	float ndotv = max(0., dot(normal, viewDir) );
	float specularFactor = pow(ndotv, roughnessE );

}