# Autotune.cmake — Drop-in CMake Integration Module for Autotune
# Allows any modern CMake project to optimize hot compute kernels with Autotune.
#
# Usage:
#   include(cmake/Autotune.cmake)
#   autotune_optimize_target(
#       TARGET my_compute_target
#       SOURCE src/kernel.c
#       PRESET balanced
#   )

cmake_minimum_required(VERSION 3.20)

find_program(AUTOTUNE_EXECUTABLE autotune REQUIRED)
find_program(AUTOTUNE_CLANG clang REQUIRED)
find_program(AUTOTUNE_OPT opt REQUIRED)

function(autotune_optimize_target)
    set(options STRICT_ENV NO_LLM)
    set(oneValueArgs TARGET SOURCE PRESET THRESHOLD)
    set(multiValueArgs EXTRA_FLAGS)
    cmake_parse_arguments(AUTOTUNE "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    if(NOT AUTOTUNE_TARGET)
        message(FATAL_ERROR "autotune_optimize_target requires TARGET argument.")
    endif()

    if(NOT AUTOTUNE_SOURCE)
        message(FATAL_ERROR "autotune_optimize_target requires SOURCE argument.")
    endif()

    set(OPT_PRESET "balanced")
    if(AUTOTUNE_PRESET)
        set(OPT_PRESET "${AUTOTUNE_PRESET}")
    endif()

    get_filename_component(SRC_STEM ${AUTOTUNE_SOURCE} NAME_WE)
    set(REPORT_JSON "${CMAKE_CURRENT_BINARY_DIR}/${SRC_STEM}_autotune_report.json")
    set(APPLIED_DIR "${CMAKE_CURRENT_BINARY_DIR}/${SRC_STEM}_artifacts")
    set(OPT_BC "${APPLIED_DIR}/${SRC_STEM}.opt.bc")

    add_custom_target(
        autotune_${AUTOTUNE_TARGET}_run
        COMMAND ${AUTOTUNE_EXECUTABLE} doctor ${AUTOTUNE_SOURCE} --preset ${OPT_PRESET} -o ${REPORT_JSON}
        COMMAND ${AUTOTUNE_EXECUTABLE} apply ${REPORT_JSON} --output-dir ${APPLIED_DIR}
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        COMMENT "Running Autotune AI-guided phase ordering on ${AUTOTUNE_SOURCE}"
    )

    message(STATUS "Autotune: Configured optimization target autotune_${AUTOTUNE_TARGET}_run for ${AUTOTUNE_SOURCE}")
endfunction()
