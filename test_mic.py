import pyaudio

p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=i,
                frames_per_buffer=1024
            )
            data = stream.read(1024, exception_on_overflow=False)
            stream.stop_stream()
            stream.close()
            print('WORKS: [' + str(i) + '] ' + info['name'])
        except Exception as e:
            print('FAIL:  [' + str(i) + '] ' + info['name'] + ' -> ' + str(e))
p.terminate()