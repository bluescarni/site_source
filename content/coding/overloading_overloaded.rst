Overloading overloaded
######################

:tags: c++,coding
:summary: Template-based, SFINAE-friendly compile-time multiple dispatch with C++11

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

The solution adopted in Piranha starts from where the aforementioned `GotW`_ ends. There is a single
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
metaprogramming techniques involving the detection of the availability of a function at compile-time.

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
* the technique is nonintrusive: user-defined types are not required to derive from a common base class or to
  implement specific methods in order to be usable by our generic ``cos()`` function.
  They will only need to provide an additional specialisation of the implementation functor;
* the technique is SFINAE-friendly: in case the ``cos_impl`` specialisation is missing, the ``cos()`` function
  is removed from the overload resolution set;
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
=====================================================

One of the points mentioned above is the "SFINAE-friendliness" of the solution: in case of a missing
``cos_impl`` specialisation, the ``cos()`` function is removed from the overload resolution set. We can use this
property to implement a type trait that detects the availability of a ``cos()`` for a specific type at compile-time.

A possible, C++11-oriented way of implementing such a type trait (by no means the only one) is the following:

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

Without getting into the details of the implementation (the interested reader can use this `Wikibooks page`_
as a starting point), the important takeaway is that now

.. code-block:: c++

   has_cosine<double>::value

is a compile-time constant with ``true`` value, while

.. code-block:: c++

   has_cosine<int>::value

is a compile-time constant with ``false`` value. In Piranha, most generic functions are paired with a
type trait that determines at compile-time whether it is possible or not to call the function with
a specific set of argument types. Such type traits become then the basic building blocks of compile-time
algorithms that, for instance, can select different implementations of a specific functionality based
on the capabilities offered by the involved types.

.. _Wikibooks page: http://en.wikibooks.org/wiki/More_C%2B%2B_Idioms/Member_Detector

A step further: exploiting the default implementation
*****************************************************

In the example above, it does not make much sense to provide a default implementation for cosine, and thus
the unspecialised ``cos_impl`` functor does not implement any call operator. For other operations, however,
a default implementation might actually make sense.

Consider for instance the classic `multiply-accumulate operation`_ (FMA for short). Since it is at the basis of so many algorithms,
from linear algebra to symbolic manipulation, many libraries provide optimised implementations of this primitive.
A few examples:

* the `C++ standard library`_ offers ``std::fma()``, usable with floating-point types;
* the `GMP library`_ offers ``mpz_addmul()``;
* the `MPFR library`_ offers ``mpfr_fma()``.

.. _multiply-accumulate operation: http://en.wikipedia.org/wiki/Multiply%E2%80%93accumulate_operation
.. _C++ standard library: http://en.cppreference.com/w/cpp/numeric/math/fma
.. _GMP library: https://gmplib.org/manual/Integer-Arithmetic.html
.. _MPFR library: http://www.mpfr.org/mpfr-current/mpfr.html#Special-Functions

The use of a specialised FMA operation can typically result in increased performance and/or accuracy.
In a generic scientific library it thus makes sense to try to take advantage of such a feature, if
available.

On the other hand, a specialised FMA is an optimisation: it would be nice not to force the user of the library
to implement the FMA primitive for her user-defined type, if for any reason she is not interested in it. The FMA operation, after all,
is essentially equivalent to

.. math::

   a \leftarrow a + ( b \times c )

so it can be implemented also in terms of addition, multiplication and assignment.

In Piranha, the FMA operation is called ``multiply_accumulate()``, and its implementation reads:

.. code-block:: c++

   template <typename T>
   inline auto multiply_accumulate(T &x, const T &y, const T &z) ->
      decltype(multiply_accumulate_impl<T>()(x,y,z))
   {
      return multiply_accumulate_impl<T>()(x,y,z);
   }

The default implementation functor is:

.. code-block:: c++

   template <typename T, typename = void>
   struct multiply_accumulate_impl
   {
      template <typename T2>
      auto operator()(T2 &x, const T2 &y, const T2 &z) const -> decltype(x += y * z)
      {
         return x += y * z;
      }
   };

(More on that second template parameter ``T2`` in a moment)

The call operator of the default implementation is now present, and it implements the FMA operation in terms of multiplication
and in-place addition. Any type which supports these two operations (e.g., ``int``) will thus have a working FMA implementation.

We can now specialise the behaviour for, e.g., floating point types:

.. code-block:: c++

   template <typename T>
   struct multiply_accumulate_impl<T,typename std::enable_if<std::is_floating_point<T>::value>::type>
   {
      auto operator()(T &x, const T &y, const T &z) const -> decltype(x = std::fma(y,z,x))
      {
         return x = std::fma(y,z,x);
      }
   };

What happens when we try to call the default implementation on a type which does not support addition, multiplication or
assignment? Let's try an FMA on ``std::string``:

.. code-block:: bash

   error: no matching function for call to ‘multiply_accumulate(std::string&, std::string&, std::string&)’

It looks like the ``multiply_accumulate()`` function for ``std::string`` has been erased, and there is no reference to the missing
``*`` operator for ``std::string``. How does this happen? The answer is in the implementation of the call
operator in the default implementation of ``multiply_accumulate_impl``:

.. code-block:: c++

   template <typename T2>
   auto operator()(T2 &x, const T2 &y, const T2 &z) const -> decltype(x += y * z)
   {
      return x += y * z;
   }

This operator is a template method which deduces its return type from the expression ``x += y * z``. As such, if the
expression ``x += y * z`` is ill-formed, then the call operator is, under SFINAE rules, removed from the overload resolution set,
and ``multiply_accumulate_impl`` is effectively left without a call operator. The top-level ``multiply_accumulate()`` function
will then see, when called with ``std::string`` arguments, a ``multiply_accumulate_impl`` functor with no call operator, and thus
SFINAE rules will also remove the ``multiply_accumulate()`` function from the overload resolution set. The compiler's error
message lamenting the lack of a suitable ``multiply_accumulate()`` function is thus explained. This also means that, even in the
presence of a default implementation, it will still be possible to write a type trait to detect the availability
of ``multiply_accumulate()``, in the same fashion as done above for ``has_cosine``.

Generalising to multiple arguments
**********************************

The two examples we have seen so far involve specialisation based on a single type (``cos()`` is a single-argument function,
``multiply_accumulate()`` operates on three arguments of the same type by design). It is however clear that the patterns described
above can readily be generalised to functions accepting multiple arguments of different types.

An obvious example is exponentiation, ``pow()``, which is a function of two arguments: a base and an exponent.
In Piranha, the ``pow()`` function has different implementations depending on the involved types. A few examples:

* if both the base and the exponent are C++ arithmetic types and at least one of the two arguments is a floating-point type,
  then ``std::pow()`` is used;
* if at least one argument is an ``integer`` (an arbitrary precision integral type implemented on top of GMP) and the other
  is an ``integer`` or a C++ integral type, then the exact result will be returned as an ``integer`` (computed via a GMP routine);
* if an argument is an ``integer`` and the other one is a floating-point type, then the ``integer`` argument is converted to
  the floating-point type and the result computed via ``std::pow()``;
* if the two arguments are both C++ integral types, then the exact result is returned as an ``integer``.

The implementation of Piranha's ``pow()`` function is too long to be reproduced here. It is avaiable from the `Git repository`_ for the
interested reader. As in the previous examples, the implementation is SFINAE-friendly and lends itself to compile-time introspection
via a type trait.

.. _Git repository: https://github.com/bluescarni/piranha/blob/4d600d04b48af3ce241d91d2f8f0fde45f822872/src/pow.hpp

Closing remarks
***************

SFINAE-based template metaprogramming in C++11 can be used to introduce a flexible and efficient method of compile-time function dispatching based
on partial class template specialisation. The method is nonintrusive, it has no runtime CPU or memory overhead, it sidesteps some problematic aspects
of function overloading, and it allows to select different
implementations of the same function for different combinations of argument types. The selection can be based either on exact type
matching or, more generally, on logical compile-time predicates on the involved types. The technique is SFINAE-friendly and lends itself
to compile-time introspection.
