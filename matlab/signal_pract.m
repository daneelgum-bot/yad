clear;
num_imp = input('Число импульсов в пачке: ');
time_imp = input('Длительность импульса: ');
imp_freq = input('Частота повторений импульса: ');
shape = input('Форма огибающей (прям или синус): ', 's');
ampl = input('Амплитуда огибающей единичного импульса: ');
fill_freq = input('Частота заполнения импульса: ');
phase = input('Начальная фаза импульсов: ');
dis_freq = input('Частота дискретизации: ');
sigma = input('Дисперсия шума: ');

graph2=input('Какие графики построить?\n1 - полезный сигна;, 2 - помеха; 3 - аддитивная смесь; 4 - одиночный импульс; 5 - спектр; 6 - Согласованная фильтрация\nВвод ', 's');

phase=deg2rad(phase);

if (1/imp_freq > time_imp) & (min([num_imp time_imp imp_freq fill_freq dis_freq sigma])) > 0 ...
        & (strcmp(shape, 'прям') | strcmp(shape, 'син'))
   
    N=fix(time_imp*dis_freq); %кол-во импульсов на один импульс
    NT=fix(dis_freq/imp_freq); %кол-во отсчетов на период
    time=0:1/dis_freq:num_imp/imp_freq;
    nn=0:1:N-1; %массив отсчетов на один импульс
    
    A(1:N)=ampl;
    if strcmp(shape,'син')
         A(1:N)=ampl*sin(nn/dis_freq*pi/time_imp);
    end
    
    A(N+1:NT)=0;
    A=[repmat(A,1,num_imp) zeros(1, length(time)-length(A)*num_imp)];
    n=0:1:length(A)-1;
    x=A.*cos(2*pi*fill_freq*n/dis_freq+phase);
    noise = sqrt(sigma)*randn(size(time));
    add_signal=noise+x;
    
    plots=sscanf(graph2, '%d');
    
    if ismember(1, plots)
        figure(1);
        plot(time, A)
        hold on;
        plot(time, x)
        legend('Огибающая','Сигнал')
        title('Полезный сигнал')
        xlabel('Время, с')
        ylabel('Сигнал, В')
        axis([0 num_imp/imp_freq min(add_signal) max(add_signal)+1])
        hold off
        grid on
    end
    
    if ismember(2, plots)
        figure(2);
        plot(time, noise)
        title('Помеха')
        xlabel('Время, с')
        ylabel('Сигнал, В')
        xlim([0 num_imp/imp_freq])
        grid on;
    end
       
    
    if ismember(3, plots)
        figure(3);
        plot(time, add_signal)
        title('Аддитивная смесь полезного сигнала и помехи')
        xlabel('Время, с')
        ylabel('Сигнал, В')
        xlim([0 num_imp/imp_freq])
        grid on;
    end
    
    if ismember(4,plots)
        figure(4)
        plot(time, A)
        hold on;
        plot(time, x)
        legend('Огибающая', 'Сигнал')
        title('Одиночный импульс')
        xlabel('Время, с')
        ylabel('Сигнал, В')
        axis([0 time_imp min(add_signal) max(add_signal)+1])
        grid on
        hold off
    end
    
    if ismember(5, plots)
    figure(5);
    L = length(x);                     % длина полезного сигнала
    NFFT = 2^nextpow2(L);              % ближайшая степень 2 (оптимально для БПФ)
    X = fft(x, NFFT);                  % комплексный спектр
    f_axis = (-NFFT/2 : NFFT/2-1) * (dis_freq / NFFT);  % ось частот со сдвигом
    plot(f_axis, fftshift(abs(X)/L));  % модуль нормированного спектра
    title('Амплитудный спектр полезного сигнала');
    xlabel('Частота, Гц');
    ylabel('|X(f)|');
    grid on;
    end
    
    
    if ismember(6, plots)
        h = fliplr(x(1:N));                  % импульсная характеристика
        y = conv(add_signal, h, 'full');
        y_matched = y(1:length(time)); 

        figure(6);
        plot(time, y_matched);
        title('Выход согласованного фильтра');
        xlabel('Время, с'); ylabel('Амплитуда');
        grid on;
    end

    
else
    disp('Error')
end
        