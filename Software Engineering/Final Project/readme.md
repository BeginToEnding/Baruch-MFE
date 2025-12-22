
executionservice.cpp add a function:
template<typename T>
PricingSide ExecutionOrder<T>::GetSide() const
{
	return side;
}
