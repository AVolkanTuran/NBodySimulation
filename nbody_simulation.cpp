#include <vector>
#include <cmath>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <random>

using namespace std;

const double G = 1.0;          // Gravitational constant, set to 1 for simplicity, but the real value is 6.67E-11
const double dt = 0.001;       // Time step
const double eps = 0.01;       // Softening parameter

struct Body {
    double mass;
    double radius;
    double x, y;
    double vx, vy;
    double ax, ay;
};

void calc_acc(vector<Body>& bodies){

    int N = bodies.size();

    //Calculate pairwise accelerations and add them up. This is where parallelization comes in.
    #pragma omp parallel for
    for(int i = 0; i < N; i++){
        //Reset accelerations each time step
        bodies[i].ax = 0.0;
        bodies[i].ay = 0.0;

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

void collide(vector<Body>& bodies, double e = 1.0){
    int N = bodies.size();

    for(int i = 0; i < N; i++){
        for(int j = i+1; j < N; j++){
            //Find the distance to every other body
            double dx = bodies[j].x - bodies[i].x;
            double dy = bodies[j].y - bodies[i].y;

            double dist_sq = dx*dx + dy*dy;

            double radii_sum = bodies[i].radius + bodies[j].radius;

            //If the distance squared between two bodies is less than their radii_sum squared,
            //Then there is a collision
            if(dist_sq >= radii_sum*radii_sum){
                continue;
            }

            double dist = sqrt(dist_sq);

            //Find the normal vector to the collision
            double nx, ny;
            if(dist > 1e-12){
                nx = dx / dist;
                ny = dy / dist;
            }
            else{
                // Handle bodies at exactly the same position
                nx = 1.0;
                ny = 0.0;
                dist = 0.0;
            }

            double inv_mi = 1.0 / bodies[i].mass;
            double inv_mj = 1.0 / bodies[j].mass;

            double inv_reduced_mass = inv_mi + inv_mj;

            double overlap = radii_sum - dist;

            //Fix their positions after collision so they aren't overlapping anymore
            bodies[i].x -= nx * overlap * inv_mi / inv_reduced_mass;
            bodies[i].y -= ny * overlap * inv_mi / inv_reduced_mass;

            bodies[j].x -= nx * overlap * inv_mj / inv_reduced_mass;
            bodies[j].y -= ny * overlap * inv_mj / inv_reduced_mass;

            //Calculate relative velocity
            double rvx = bodies[j].vx - bodies[i].vx;
            double rvy = bodies[j].vy - bodies[i].vy;

            //Calculate relative velocity along collision normal
            double velocity_normal = rvx * nx + rvy * ny;

            //Only apply impulse if bodies are approaching each other
            if(velocity_normal < 0.0){

                double J = -(1.0 + e) * velocity_normal / inv_reduced_mass;

                // Update velocities
                bodies[i].vx -= J * nx * inv_mi;
                bodies[i].vy -= J * ny * inv_mi;

                bodies[j].vx += J * nx * inv_mj;
                bodies[j].vy += J * ny * inv_mj;
            }
        }
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

double valid_restitution(const string& value) {
    size_t consumed;
    double result = stod(value, &consumed);

    if (consumed != value.size() || !isfinite(result) ||
        result < 0.0 || result > 1.0) {
        throw invalid_argument("Coefficient of restitution must be between 0 and 1: " + value);
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

vector<Body> solar_system() {
    // Masses in solar masses, distances in AU; angles are illustrative, not ephemerides.
    const double masses[] = {1.660e-7, 2.447e-6, 3.003e-6, 3.227e-7,
                             9.545e-4, 2.858e-4, 4.366e-5, 5.151e-5};
    const double distances[] = {0.387, 0.723, 1.0, 1.524, 5.203, 9.537, 19.191, 30.069};
    const double angles[] = {0.0, 1.1, 2.2, 3.3, 4.0, 5.0, 5.7, 0.7};
    const double radii[] = {0.0000163, 0.00004045, 0.000042635, 0.00002266, 0.0004779, 0.0004027, 0.0001708, 0.000165};
    vector<Body> bodies;
    bodies.push_back({1.0, 0.00465047, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0});
    for (size_t i = 0; i < 8; i++) {
        double r = distances[i];
        double c = cos(angles[i]);
        double s = sin(angles[i]);
        // Circular two-body speed for the same softened force used by calc_acc.
        double speed = sqrt(G * (1.0 + masses[i]) * r * r /
                            pow(r * r + eps * eps, 1.5));
        bodies.push_back({masses[i], radii[i], r * c, r * s, -speed * s, speed * c, 0.0, 0.0});
    }

    double total_mass = 0.0, x = 0.0, y = 0.0, vx = 0.0, vy = 0.0;
    for (const Body& body : bodies) {
        total_mass += body.mass;
        x += body.mass * body.x;
        y += body.mass * body.y;
        vx += body.mass * body.vx;
        vy += body.mass * body.vy;
    }
    for (Body& body : bodies) {
        body.x -= x / total_mass;
        body.y -= y / total_mass;
        body.vx -= vx / total_mass;
        body.vy -= vy / total_mass;
    }
    return bodies;
}

int run(int argc, char* argv[]) {
    int steps = 10000;
    int sample_every = 10;
    double e = 1.0;
    string output_path;
    string preset = "default";
    for (int i = 1; i < argc; i++) {
        string option = argv[i];
        if (option == "--help") {
            cout << "Usage: nbody_simulation [--output trajectory.csv]"
                 << " [--steps 10000] [--sample-every 10]"
                 << " [--preset default|solar-system] [--e 1.0]\n";
            return 0;
        }
        if (option != "--output" && option != "--steps" &&
            option != "--sample-every" && option != "--preset" && option != "--e") {
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
        } else if (option == "--preset") {
            preset = argv[i];
            if (preset != "default" && preset != "solar-system") {
                throw invalid_argument("Unknown preset: " + preset);
            }
        } else if (option == "--steps") {
            steps = positive_integer(argv[i]);
        } else if (option == "--e") {
            e = valid_restitution(argv[i]);
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
    vector<Body> bodies;
    if (preset == "solar-system") {
        bodies = solar_system();
    } else {
        //Random particle scenario.
        const int N = 1000;
        bodies.resize(N);

        //Random number generator
        random_device rd;
        mt19937 gen(rd());

        //Initial positions: uniform distribution in a square
        uniform_real_distribution<double> position(-10.0, 10.0);

        //Initial velocities: normal distribution
        normal_distribution<double> velocity(0.0, 0.5);

        for (int i = 0; i < N; i++) {
            bodies[i].mass = 0.01;
            bodies[i].radius = 0.02;

            bodies[i].x = position(gen);
            bodies[i].y = position(gen);

            bodies[i].vx = velocity(gen);
            bodies[i].vy = velocity(gen);

            bodies[i].ax = 0.0;
            bodies[i].ay = 0.0;
        }
    }

    if (output.is_open()) {
        write_frame(output, bodies, 0);
    }
    for(int step = 0; step < steps; step++){
        calc_acc(bodies);
        advance(bodies);
        collide(bodies, e);

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