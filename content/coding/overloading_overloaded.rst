Overloading overloaded
######################

:tags: c++,coding
:summary: Template-based, SFINAE-friendly multiple dispatching with C++11

Introduction and motivation
***************************

The fundamental idea of generic programming is that
of writing classes, algorithms and functions able to
operate on arbitrary types. In the jargon of modern C++, one says that
a software component defines a *concept* (i.e., a set of requirements)
of which a type ``T`` must be a *model* in order for ``T`` to be usable
with that component.

Take for instance the ``std::sort()`` function from the standard C++ library.
One of its prototypes `reads`_:

.. code-block:: c++

   template <class RandomIt>
   void sort(RandomIt first, RandomIt last);

.. _reads: http://en.cppreference.com/w/cpp/algorithm/sort

Among others, one of the requirements stipulated by ``std::sort()`` is that
the value type of ``RandomIt`` (that is, the type we are sorting) must be equipped
with a less-than operator (``std::sort()`` is a `comparison sort`_).
It is thus possible to sort out-of-the-box, for instance, vectors of integers
or floating point values (`disregarding NaNs`_ for a second). It will not however
be possible to sort instances of ``std::complex``, as ``operator<()`` is not implemented
for these types (C++ wisely does not get into the business of defining an ordering relation
for complex numbers).

.. _comparison sort: http://en.wikipedia.org/wiki/Comparison_sort
.. _disregarding NaNs: http://stackoverflow.com/questions/14784263/stdout-of-range-during-stdsort-with-custom-comparator

If the type we are sorting does not provide an ``operator<()``, we have a couple of possible options.

The first option is to use the other version of ``std::sort()`` provided by the standard library,
which reads:

.. code-block:: c++

   template <class RandomIt, class Compare>
   void sort(RandomIt first, RandomIt last, Compare comp);

Here the additional parameter ``comp`` must be a function-like object able to compare
instances of the value type according to some strict weak ordering relation
(here are the `gory details`_ in their standardese glory). This basically means
that we can tell ``std::sort()`` *how* instances of the value type should be compared
for sorting purposes. In the case of complex numbers, we might want to sort a vector
of complex values according to their norm, or maybe to their real or imaginary component,
depending on the context.

.. _gory details: http://en.cppreference.com/w/cpp/concept/Compare

The second option is to equip a type with an appropriate ``operator<()`` implementation
via `operator overloading`_. While for ``std::complex`` this is probably not a good idea
(due to the lack of a "natural" ordering for complex numbers),
for other types it is certainly an appropriate solution.

.. _operator overloading: http://en.wikipedia.org/wiki/Operator_overloading

Now, one of the challenges I faced with
`Piranha`_ was related to the design of a generic and user-extensible
library of mathematical functions. As a simple example, consider the expression

.. math::

  \frac{1}{2}x\cos\left(\alpha+\beta\right).

.. _Piranha: https://github.com/bluescarni/piranha

This is a `Poisson series`_ that Piranha can represent symbolically. In order to evaluate
this expression for specific numerical values of the variables :math:`x`, :math:`\alpha`
and :math:`\beta`, we need to be able to compute the cosine of those numerical values.
The way in which the cosine is computed will depend on the type we use for evaluation:
if we use standard C++ floating-point types (``float``, ``double`` and ``long double``),
we probably want to use the standard ``std::cos()`` function. But, if we need more precision,
we might implement a custom multiple-precision floating-point type (or, more likely, write a C++
wrapper around `MPFR`_). We are then faced with the task of informing Piranha about
*how* to evaluate the cosine function for our brand new multiprecision floating-point type.

.. _Poisson series: http://www.sciencedirect.com/science/article/pii/S0747717100903961
.. _MPFR: http://www.mpfr.org/

A possible solution to this problem is to use the the mechanism of `function overloading`_. However,
an overloading-based approach suffers from a few shortcomings. For starters,
the `overloading rules`_ in C++ are notoriously complicated. The interactions between
function overloads, templates, and specialisations can often be counterintuitive, as explained
in this classic `GotW`_ by Herb Sutter. Function overloading is also sensitive to declaration
order and interacts with implicit conversions.

Piranha aims to be a completely generic system, open to extensions via user-defined custom types
(such as the hypothetical multiprecision floating-point type above) the core library knows nothing
about. After some initial
experiments, it became clear that a purely overloading-based solution was not good enough
to realise this goal and that an alternative approach was necessary.

.. _function overloading: http://en.wikipedia.org/wiki/Function_overloading
.. _GotW: http://www.gotw.ca/publications/mill17.htm
.. _overloading rules: http://en.cppreference.com/w/cpp/language/overload_resolution

A generic ``cos()`` implementation
**********************************

The solution adopted in Piranha takes inspiration from the aforementioned `GotW`_. There is a single
generic ``cos()`` function in the ``math`` sub-namespace which looks like this:

.. code-block:: c++

   namespace math
   {

   template <typename T>
   inline auto cos(const T &x) -> decltype(cos_impl<T>()(x))
   {
       return cos_impl<T>()(x);
   }

   }

The function forwards the computation to an helper template class called ``cos_impl``, which is parametrised
over the type ``T`` of the argument ``x`` and expected to provide a call operator to which the original
argument ``x`` is passed. The return type of ``cos()`` is automatically deduced from the call operator
of ``cos_impl``. The default implementation of ``cos_impl`` is an empty class:

.. code-block:: c++

   namespace math
   {

   template <typename T, typename = void>
   struct cos_impl
   {};

   }

The second "ghost" template parameter, unnamed and defaulting to ``void``, is there to allow the use of
the `enable-if mechanism`_. We can then provide a specialisation of ``cos_impl`` for C++ floating-point types,
which reads:

.. code-block:: c++

   namespace math
   {

   template <typename T>
   struct cos_impl<T,typename std::enable_if<std::is_floating_point<T>::value>::type>
   {
       auto operator()(const T &x) const -> decltype(std::cos(x))
       {
           return std::cos(x);
       }
   };

   }

.. _enable-if mechanism: http://en.cppreference.com/w/cpp/types/enable_if

That is, whenever ``cos_impl`` is instantiated with a type ``T`` which is a floating-point type, the
second (specialised) implementation will be selected. If now we try to call the ``cos()`` function with,
let's say, an argument of type ``double``, the call will ultimately be forwarded to ``std::cos()`` as expected.

Now, what happens when we call ``cos()`` with an ``int`` argument? The specialisation of ``cos_impl``
comes into play only when ``T`` is a floating-point type, thus an ``int`` argument will be forwarded to the
unspecialised default ``cos_impl`` functor. The unspecialised ``cos_impl`` does not provide any call operator,
and thus a compile-time error will arise. GCC 5.1 says:

.. code-block:: bash

   $ g++-5.1.0 -std=c++11 cos.cpp
   [...]
   error: no matching function for call to ‘cos(int)’
   [...]

As you can see there is no reference in the error message about a missing call operator. The compiler actually
complains that there is no ``cos()`` function which takes an argument of type ``int``. What happens here is that
the declaration of the ``cos()`` function,

.. code-block:: c++

   template <typename T>
   inline auto cos(const T &x) -> decltype(cos_impl<T>()(x));

generates an error due to the fact that the expression ``cos_impl<T>()(x)`` is ill-formed
when ``T`` is ``int`` (because of the
missing call operator in the default ``cos_impl`` implementation). This error is
treated specially due to a set of rules that go under the name of `SFINAE`_ (substitution failure is not an error):
instead of generating a "hard" compiler error, the function that triggered the failure is simply *removed*.
For all practical purposes, it is as-if the ``cos()`` function had been erased from the source code, when invoked with
an argument of type ``int``. The error resulting from the
compilation thus originates from the missing ``cos()`` function rather than from the missing call operator. The distinction
between these two types of error might appear academic at first sight (after all, we end up in both cases with an aborted
compilation), but it is crucial for the development of further
metaprogramming techniques involving the detection of the availability of a function at compile time.

.. _SFINAE: http://en.cppreference.com/w/cpp/language/sfinae#Expression_SFINAE

What have we gained so far?
***************************

The technique described above for the implementation of a generic, user-extensible ``cos()`` function has a few
interesting features:

* it is entirely based on compile-time metaprogramming: no virtual functions, no calling overhead, easily optimisable
  by any modern compiler;
* we avoid the headaches of function overloading: there is exactly one entry point, completely generic;
* by using class template specialisation instead of overloading, the order in which the specialisations are declared
  does not matter (the compiler must consider all the visible template specialisations before choosing one);
* we are also avoiding surprises with implicit conversions: the example above shows how the implementation
  is based on exact type matching - use with an ``int`` argument will result in a compilation error, even if
  ``int`` instances are implicitly convertible to floating-point types;
* the technique is non-intrusive: user-defined types are not required to derive from a common base class or to
  implement specific methods in order to be usable by our generic ``cos()`` function.
  They will only need to provide an additional specialisation of the implementation functor;
* unlike with normal function overloading, we can specialise the behaviour not only based on concrete types, but
  on arbitrary compile-time *predicates*.

The last point is, I think, particularily interesting. It is not unusal in scientific C++ libraries to see either

* heavy usage of macros to declare and define multiple overloads of the same function with different
  argument types (``float``, ``double``, ``long``, etc.), or
* functions implemented in terms of "wide" types (e.g., ``long double`` and ``long long``) that can be used with
  narrower types (e.g., ``float`` and ``int``) via implicit conversions.

With this approach, any compile-time predicate that produces a boolean value can be used to specialise the
implementation. In the example above, we used the predicate

.. code-block:: c++

   std::is_floating_point<T>::value

in order to specialise the implementation for floating-point types. In the same fashion, we could implement a generic
``abs()`` function that, for instance, returns the input argument unchanged when invoked on unsigned integer types.
The specialisation in this case would use the predicate:

.. code-block:: c++

   std::is_integral<T>::value && std::is_unsigned<T>::value

This predicate would catch all the standard unsigned `integral types`_ available in C++.

.. _integral types: http://en.cppreference.com/w/cpp/language/types#Integer_types

Intermission: detecting the availability of ``cos()``
*****************************************************

.. code-block:: c++

   template <typename T>
   class has_cosine
   {
           struct yes {};
           struct no {};
           template <typename T1>
           static auto test(const T1 &x) -> decltype(math::cos(x),void(),yes());
           static no test(...);
       public:
           static const bool value = std::is_same<decltype(test(std::declval<T>())),yes>::value;
   };
