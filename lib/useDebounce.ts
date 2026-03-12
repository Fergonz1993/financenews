import { useCallback, useEffect, useRef, useState } from 'react';

export function useDebounce<T>(value: T, delay: number): [T, (nextValue?: T) => void] {
  const [debouncedValue, setDebouncedValue] = useState(value);
  const latestValueRef = useRef(value);

  useEffect(() => {
    latestValueRef.current = value;
  }, [value]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [delay, value]);

  const flush = useCallback((nextValue?: T) => {
    setDebouncedValue(nextValue ?? latestValueRef.current);
  }, []);

  return [debouncedValue, flush];
}
