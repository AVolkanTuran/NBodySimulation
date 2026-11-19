cmake_minimum_required(VERSION 3.10)
project(NBodySimulation)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(nbody_simulation nbody_simulation.cpp)

find_package(OpenMP REQUIRED)
target_link_libraries(nbody_simulation PRIVATE OpenMP::OpenMP_CXX)

if(MSVC)
    target_compile_options(nbody_simulation PRIVATE /W4 /O2)
else()
    target_compile_options(nbody_simulation PRIVATE -Wall -O2 -Wextra)
endif()

if(MINGW)
    target_link_libraries(nbody_simulation PRIVATE -static-libgcc -static-libstdc++)
endif()