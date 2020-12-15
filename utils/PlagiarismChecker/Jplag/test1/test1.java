public class test1 {

    public static void main(String[] args) {

        int[] data = { 4, 54, 2, 8, 63, 7, 55, 56 };
        int temp;
        int cnt = 0;

        System.out.print("======정렬 전===============\n");
        for(int m=0; m<data.length; m++) {
            System.out.print(data[m] + ", ");

        }

        for(int i=data.length; i>0; i--) {
            //
            for (int j=0; j<i-1; j++) {
                cnt++;
                if(data[j] > data[j+1]) {
                    temp = data[j];
                    data[j] = data[j+1];
                    data[j+1] = temp;
                }
            }
        }

        System.out.print("\n\n======Bubble Sort=========\n");
        for(int k=0; k<data.length; k++) {
            System.out.print(data[k] + ", ");

        }
        System.out.println("\n\n 총 회전 수 : " + cnt);
    }
}