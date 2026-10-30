# Boost.JSON uses Boost.Container's polymorphic memory resources. Resolve the
# actual library through CMake rather than relying on MSVC's pragma autolink.
find_package(Boost REQUIRED COMPONENTS container)
target_link_libraries(modules PUBLIC Boost::container)
