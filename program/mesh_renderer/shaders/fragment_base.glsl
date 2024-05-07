in vec3 normal;
in vec2 tcs;
in vec3 p;
out vec4 fragColor;

void main(void)
{
	fragColor = vec4(normal + tcs.xxx + p, 1.);
}