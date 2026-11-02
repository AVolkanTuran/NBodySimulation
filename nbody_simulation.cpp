#include <vector>
#include <cmath>
#include <iostream>

using namespace std;

const double G = 1.0;          // Gravitational constant, set to 1 for simplicity, but the real value is 6.67E-11
const double dt = 0.001;       // Time step
const double eps = 0.01;       // Softening parameter

struct Body {
    double mass;
    double x, y;
    double vx, vy;
    double ax, ay;
};

void calc_acc(vector<Body>& bodies){

    int N = bodies.size();

    //Reset accelerations each time step
    for(Body& body : bodies){
        body.ax = 0.0;
        body.ay = 0.0;
    }

    //Calculate pairwise accelerations and add them up
    for(int i = 0; i < N; i++){
        for(int j = 0; j < N; j++){
            if(i == j){
                continue;
            }

            double dx = bodies[j].x - bodies[i].x;
            double dy = bodies[j].y - bodies[i].y;

            double rsquared = dx*dx + dy*dy + eps*eps; //eps^2 added for softening
            double denominator = pow(rsquared, 1.5); //The denominator is (rsquared)^3/2

            //Update the accelerations
            bodies[i].ax += G * bodies[j].mass * dx / denominator;
            bodies[i].ay += G * bodies[j].mass * dy / denominator;
        }
    }

}

void advance(vector<Body>& bodies){
    for(Body& body : bodies){
        body.vx += body.ax * dt;
        body.vy += body.ay * dt;

        body.x += body.vx * dt;
        body.y += body.vy * dt;
    }
}

int main() {

    //Just for test purposes for now
    const int N = 100;
    const int STEPS = 10000;

    vector<Body> bodies(N);

    for (int i = 0; i < N; i++) {
        bodies[i].mass = 10;
        bodies[i].x = pow(-1, i)*i/100.0;
        bodies[i].y = pow(-1, i)*i/100.0;
        bodies[i].vx = 0.0;
        bodies[i].vy = 0.0;
        bodies[i].ax = 0.0;
        bodies[i].ay = 0.0;
    }

    for(int step = 0; step < STEPS; step++){
        calc_acc(bodies);
        advance(bodies);

        if (step % 100 == 0) {
            cout << "Step: " << step << endl;
            cout << "Body 1 X: " << bodies[0].x << ", Y: " << bodies[0].y << endl;
        }
    }
}