cmake_minimum_required(VERSION 3.10)
project(NBodySimulation)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "-Wall -O2 -Wextra")

add_executable(nbody_simulation nbody_simulation.cpp)