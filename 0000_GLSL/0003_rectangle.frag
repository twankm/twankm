// Author:
// Title:

#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform vec2 u_mouse;
uniform float u_time;

void main() {
    vec2 st = gl_FragCoord.xy/u_resolution.xy;
    vec3 color = vec3(0.0);
    
    vec2 borders = step(vec2(0.1), st);
    float pct = borders.x * borders.y;
    
    vec2 tr = step(vec2(0.1), 1.0 - st);
    pct *= tr.x * tr.y;
    float left = step(0.1, st.x);
    float bottom = step(0.1, st.y);
    
    color = vec3(pct);

    gl_FragColor = vec4(color,1.0);
}