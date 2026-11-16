#include <vector>
#include <cmath>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>

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

int positive_integer(const string& value) {
    size_t consumed;
    int result = stoi(value, &consumed);
    if (consumed != value.size() || result <= 0) {
        throw invalid_argument("Expected a positive integer, got: " + value);
    }
    return result;
}

void write_frame(ostream& output, const vector<Body>& bodies, int step) {
    for (size_t i = 0; i < bodies.size(); i++) {
        output << step << ',' << step * dt << ',' << i << ','
               << bodies[i].mass << ',' << bodies[i].x << ',' << bodies[i].y << '\n';
    }
    if (!output) {
        throw runtime_error("Failed to write trajectory");
    }
}

int run(int argc, char* argv[]) {
    int steps = 10000;
    int sample_every = 10;
    string output_path;
    for (int i = 1; i < argc; i++) {
        string option = argv[i];
        if (option == "--help") {
            cout << "Usage: nbody_simulation [--output trajectory.csv]"
                 << " [--steps 10000] [--sample-every 10]\n";
            return 0;
        }
        if (option != "--output" && option != "--steps" && option != "--sample-every") {
            throw invalid_argument("Unknown option: " + option);
        }
        if (++i >= argc) {
            throw invalid_argument("Missing value for " + option);
        }
        if (option == "--output") {
            output_path = argv[i];
            if (output_path.empty()) {
                throw invalid_argument("Output path must not be empty");
            }
        } else if (option == "--steps") {
            steps = positive_integer(argv[i]);
        } else {
            sample_every = positive_integer(argv[i]);
        }
    }
    ofstream output;
    if (!output_path.empty()) {
        output.open(output_path);
        if (!output) {
            throw runtime_error("Cannot open output file: " + output_path);
        }
        output << setprecision(17) << "step,time,id,mass,x,y\n";
    }
    //Just for test purposes for now
    const int N = 100;

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

    if (output.is_open()) {
        write_frame(output, bodies, 0);
    }
    for(int step = 0; step < steps; step++){
        calc_acc(bodies);
        advance(bodies);

        if (output.is_open() && ((step + 1) % sample_every == 0 || step == steps - 1)) {
            write_frame(output, bodies, step + 1);
        }
        if (step % 100 == 0) {
            cout << "Step: " << step << endl;
            cout << "Body 1 X: " << bodies[0].x << ", Y: " << bodies[0].y << endl;
        }
    }
    if (output.is_open()) {
        output.flush();
        if (!output) {
            throw runtime_error("Failed to flush trajectory: " + output_path);
        }
    }
    return 0;
}

int main(int argc, char* argv[]) {
    try {
        return run(argc, argv);
    } catch (const exception& error) {
        cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}